import logging
from typing import Callable

from langgraph.graph import StateGraph, END

from config import features
from llm.client import trace_calls
from llm.models import role_models
from pipeline.state import PipelineState
from pipeline.trace import build_trace_row
from pipeline.finalise import validation_record
from pipeline.redraft import review_summary
from pipeline.single_writer import wire_draft_only, wire_reviewed
from utils.formatters import normalise_post_punctuation, resolve_length_target
from utils.frames import decide_perspective
from memory.profile_store import load_profile
from memory.feedback_store import get_all_topics_posted
from memory.trace_store import save_generation_trace
from agents.retrieval_agent import retrieval_node
from agents.draft_agent import draft_node
from agents.critic_agent import critic_node
from agents.humanizer_agent import humanizer_node
from agents.predictability_audit_agent import predictability_audit_node
from agents.word_count_enforcer_agent import word_count_enforcer_node
from agents.fact_check_agent import fact_check_node, log_fact_check
from agents.scorer_agent import scorer_node

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 75
MAX_ITERATIONS = 3


def load_profile_node(state: PipelineState) -> PipelineState:
    user_id = state["user_id"]
    state["profile"] = load_profile(user_id=user_id)
    state["iterations"] = 0
    state["archetype"] = state.get("archetype", "")
    state["critic_brief"] = {}
    state["posted_topics"] = get_all_topics_posted(user_id=user_id)
    state["first_post"] = len(state["posted_topics"]) == 0
    return state


def plan_node(state: PipelineState) -> PipelineState:
    """Decide once, from the request and what retrieval found, the two things
    every later node works to: the post's length target and its perspective.

    Runs after retrieval because both depend on it (thin sources change the
    length target; the chunks' authorship sets the perspective).
    """
    gate = (state.get("coverage_gate") or {}).get("decision")
    state["length_target"] = resolve_length_target(
        state.get("format", ""),
        state.get("length", ""),
        first_post=bool(state.get("first_post")),
        thin_sources=state.get("retrieval_confidence") == "low",
    )
    # The notes don't cover the topic, but a post is written anyway (a first
    # post from the onboarding answers, or an opinion post without specifics).
    not_covered = bool(state.get("no_specifics")) or gate in ("skipped_first_post", "bypassed")
    state["perspective"] = decide_perspective(
        (state.get("retrieval_bundle") or {}).get("chunks", []),
        state.get("profile") or {},
        opinion_only=not_covered,
    )
    logger.info("plan: length_target=%s perspective=%s", state["length_target"], state["perspective"])
    return state


DRAFT_TRUNCATED_MESSAGE = (
    "The draft was cut off before it was finished, so there is no post to show. "
    "Generate again, or choose a shorter length."
)

DRAFT_REFUSED_MESSAGE = (
    "The model declined to write this post, so there is no post to show. "
    "Try a different topic or wording."
)

LOW_COVERAGE_SUGGESTION = (
    "Your memory doesn't cover this topic yet. Add a source about it, "
    "or write an opinion post without specifics."
)


def route_after_retrieval(state: PipelineState) -> str:
    """Stop before drafting when the knowledge base doesn't cover the topic."""
    if (state.get("coverage_gate") or {}).get("decision") == "low_coverage":
        return "low_coverage"
    return "draft"


def low_coverage_node(state: PipelineState) -> PipelineState:
    state["final_post"] = ""
    return state


def finalize_node(state: PipelineState) -> PipelineState:
    state["final_post"] = normalise_post_punctuation(state["current_draft"])
    # Record only: pipeline A's post is returned as it is, whatever this says.
    state["final_validation"] = validation_record(state["final_post"], state.get("length_target"))
    return state


def should_score(state: PipelineState) -> str:
    """Route after predictability_audit.

    polished → scorer (word_count_enforcer runs after all scoring iterations, via should_retry)
    standard / draft → word_count_enforcer (runs once as the final gate before finalize)
    """
    if state.get("quality", "standard") == "polished":
        return "scorer"
    return "word_count_enforcer"


def should_retry(state: PipelineState) -> str:
    """Route after scorer: only called for polished mode.

    Retry loop (humanizer → predictability_audit → scorer) never passes through
    word_count_enforcer — it runs exactly once when scoring is finished.
    """
    if state.get("score_error"):
        return "word_count_enforcer"
    if state.get("score", 0) < SCORE_THRESHOLD and state.get("iterations", 0) < MAX_ITERATIONS:
        return "humanizer"
    return "word_count_enforcer"


def _wire_rewrite_chain(graph: StateGraph) -> None:
    """Variant A, after plan: draft (which picks the archetype) → critic →
    humanizer → predictability_audit → (scorer loop, polished only) →
    word_count_enforcer → fact_checker → finalize."""
    graph.add_node("draft", draft_node)
    graph.add_node("critic", critic_node)
    graph.add_node("humanizer", humanizer_node)
    graph.add_node("predictability_audit", predictability_audit_node)
    graph.add_node("word_count_enforcer", word_count_enforcer_node)
    graph.add_node("fact_checker", fact_check_node)
    graph.add_node("scorer", scorer_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge("plan", "draft")
    graph.add_edge("draft", "critic")
    graph.add_edge("critic", "humanizer")
    graph.add_edge("humanizer", "predictability_audit")
    graph.add_conditional_edges(
        "predictability_audit",
        should_score,
        {
            "scorer": "scorer",
            "word_count_enforcer": "word_count_enforcer",
        },
    )
    graph.add_conditional_edges(
        "scorer",
        should_retry,
        {
            "humanizer": "humanizer",
            "word_count_enforcer": "word_count_enforcer",
        },
    )
    graph.add_edge("word_count_enforcer", "fact_checker")
    graph.add_edge("fact_checker", "finalize")
    graph.add_edge("finalize", END)


# What runs after plan, per variant (config.features.PIPELINE_VARIANTS).
# Everything up to and including plan is shared. B and C are wired in
# pipeline/single_writer.py.
_AFTER_PLAN: dict[str, Callable[[StateGraph], None]] = {
    "A": _wire_rewrite_chain,
    "B": wire_reviewed,
    "C": wire_draft_only,
}


def build_graph(variant: str):
    """The compiled pipeline for one variant: the shared nodes up to plan, then
    that variant's steps. Raises PipelineConfigError for an unknown variant."""
    wire_after_plan = _AFTER_PLAN[features.VARIANT_GRAPH[features.validate_pipeline_variant(variant)]]
    graph = StateGraph(PipelineState)

    graph.add_node("load_profile", load_profile_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("plan", plan_node)
    graph.add_node("low_coverage", low_coverage_node)

    graph.set_entry_point("load_profile")
    graph.add_edge("load_profile", "retrieval")
    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {"draft": "plan", "low_coverage": "low_coverage"},
    )
    graph.add_edge("low_coverage", END)
    wire_after_plan(graph)

    return graph.compile()


# One compiled graph per variant, built once at import. (B-Opus compiles its
# own copy of B's graph: the models are in the state, not in the graph.)
PIPELINES = {variant: build_graph(variant) for variant in features.PIPELINE_VARIANTS}


def run_pipeline(
    topic: str,
    format: str,
    tone: str,
    length: str = "standard",
    context: str = "",
    quality: str = "standard",
    *,
    user_id: str,
    no_specifics: bool = False,
    variant: str | None = None,
    models: dict[str, str] | None = None,
) -> dict:
    """Run the pipeline. Returns status "ok" with the post, status
    "low_coverage" (empty post, closest_sources, suggestion) when the coverage
    gate stops it before drafting, or status "draft_truncated" (empty post,
    message) when a single-writer draft was cut off at its output limit, or
    status "draft_refused" (empty post, message) when the draft model declined
    to write it. no_specifics=True skips the gate; it raises
    ValueError while config.features.NO_SPECIFICS_MODE_ENABLED is off.

    Under variant B an "ok" result carries review: {outcome, issues: [{type,
    sentence_text}]}, the acting issues on the returned post
    (pipeline.redraft); it is None when no review ran (A, C, and B with
    quality="draft"). Only variant A scores a post.

    STOPGAP: nothing reads `review` or the "draft_truncated" status yet: the
    Create page shows the post as if neither existed, and selection refine
    still rewrites a single-writer post with pipeline A's own writer and
    checks. Proper fix: the frontend ReviewNotice and the refine alignment,
    step 9 of docs/plans/single-writer.md.

    variant: which pipeline to run (config.features.PIPELINE_VARIANTS). None
    uses the configured one (PIPELINE_VARIANT, default A); evals pass it to
    compare variants. An unknown variant raises PipelineConfigError.

    models: evals only. Role models that replace the variant's own
    (llm.models.role_models), e.g. {"small": ...} for the small-model check. Not
    accepted under A, whose agents use fixed models."""
    if no_specifics and not features.NO_SPECIFICS_MODE_ENABLED:
        raise ValueError("no-specifics mode is disabled (config.features.NO_SPECIFICS_MODE_ENABLED)")
    variant = features.pipeline_variant() if variant is None else features.validate_pipeline_variant(variant)
    if features.VARIANT_GRAPH[variant] == "A":
        if models:
            raise ValueError("pipeline A uses fixed models; role models apply to the single-writer variants")
        single_writer_models = {}
    else:
        single_writer_models = {"models": role_models(variant, models)}
    initial_state: PipelineState = {
        "topic": topic,
        "format": format,
        "tone": tone,
        "length": length,
        "context": context,
        "quality": quality,
        "user_id": user_id,
        "variant": variant,
        **single_writer_models,
        "iterations": 0,
        "archetype": "",
        "critic_brief": {},
        "draft_history": [],
        "score_history": [],
        "specifics_guard": [],
        "no_specifics": no_specifics,
    }

    with trace_calls() as calls:
        result = PIPELINES[variant].invoke(initial_state)

    # The trace is diagnostic only: a failed write must never fail generation.
    trace_id: str | None = None
    try:
        trace_id = save_generation_trace(build_trace_row(result, calls))
    except Exception:
        logger.exception("generation trace write failed for user %s", user_id)

    # Log-only fact check (normal mode, see fact_check_agent.enforced): the caller
    # runs this after responding (/generate: BackgroundTasks; evals: after timing).
    fact_check_job = None
    if trace_id and (result.get("fact_check") or {}).get("mode") == "log_only":
        fact_check_job = lambda: log_fact_check(result, trace_id)  # noqa: E731

    gate = result.get("coverage_gate") or {}
    if gate.get("decision") == "low_coverage":
        return {
            "status": "low_coverage",
            "post": "",
            "score": 0,
            "score_feedback": [],
            "iterations": 0,
            "archetype": "",
            "scored": False,
            "retrieval_confidence": result.get("retrieval_confidence", "low"),
            "closest_sources": gate.get("closest_sources", []),
            "suggestion": LOW_COVERAGE_SUGGESTION,
            "trace_id": trace_id,
        }

    if result.get("draft_truncated") or result.get("draft_refused"):
        refused = bool(result.get("draft_refused"))
        return {
            "status": "draft_refused" if refused else "draft_truncated",
            "post": "",
            "message": DRAFT_REFUSED_MESSAGE if refused else DRAFT_TRUNCATED_MESSAGE,
            "score": 0,
            "score_feedback": [],
            "iterations": 0,
            "archetype": result.get("archetype", ""),
            "scored": False,
            "retrieval_confidence": result.get("retrieval_confidence", "medium"),
            "trace_id": trace_id,
        }

    return {
        "status": "ok",
        "post": result.get("final_post", result.get("current_draft", "")),
        "score": result.get("score", 0),
        "score_feedback": result.get("score_feedback", []),
        "iterations": result.get("iterations", 1),
        "archetype": result.get("archetype", ""),
        "scored": variant == "A" and quality == "polished" and not result.get("score_error"),
        "retrieval_confidence": result.get("retrieval_confidence", "medium"),
        "trace_id": trace_id,
        "fact_check_job": fact_check_job,
        "review": review_summary(result),
    }
