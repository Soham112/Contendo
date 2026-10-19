import logging
import time
from typing import Callable

from langgraph.graph import StateGraph, END

from config import features
from llm.client import trace_calls
from llm.models import role_models
from pipeline.state import PipelineState
from pipeline.trace import build_trace_row, timed_node
from pipeline.finalise import validation_record
from pipeline.redraft import review_summary
from pipeline.single_writer import wire_draft_only, wire_one_call, wire_reviewed
from utils.formatters import normalise_post_punctuation, resolve_length_target
from utils.business_notes import business_context
from utils.frames import decide_perspective
from memory.account_store import get_account
from memory.profile_store import load_profile
from memory.feedback_store import get_all_topics_posted
from memory.trace_store import save_generation_trace
from agents.retrieval_agent import retrieval_node
from agents.draft_agent import draft_node
from agents.critic_agent import critic_node
from agents.humanizer_agent import humanizer_node
from agents.predictability_audit_agent import predictability_audit_node
from agents.word_count_enforcer_agent import word_count_enforcer_node
from agents.fact_check_agent import fact_check_node
from agents.scorer_agent import scorer_node

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 75
MAX_ITERATIONS = 3


def load_profile_node(state: PipelineState) -> PipelineState:
    user_id = state["user_id"]
    state["profile"] = load_profile(user_id=user_id)
    account = get_account(user_id)
    business = business_context(account, state.get("pillar"))
    if business:
        state["business"] = business
        if features.business_block_enabled():
            # All downstream readers, including pipeline A, see the account identity.
            state["profile"] = {**state["profile"], "name": (account.get("business_profile") or {}).get("business_name", ""),
                                "role": business["niche_label"]}
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
        # Pipeline A, the rollback, keeps the length the request asks for.
        requested_linkedin_length=state.get("variant") == "A",
    )
    if gate == "profile_only":
        state["length_target"] = resolve_length_target(state.get("format", ""), "concise", profile_only=True)
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

DRAFT_EMPTY_MESSAGE = (
    "The model returned no post. Generate again, or try a different topic or wording."
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
    "D": wire_one_call,
}


def build_graph(variant: str):
    """The compiled pipeline for one variant: the shared nodes up to plan, then
    that variant's steps. Raises PipelineConfigError for an unknown variant."""
    wire_after_plan = _AFTER_PLAN[features.VARIANT_GRAPH[features.validate_pipeline_variant(variant)]]
    graph = StateGraph(PipelineState)

    # Every variant times the shared steps (state["step_timings"]).
    graph.add_node("load_profile", timed_node("load_profile", load_profile_node))
    graph.add_node("retrieval", timed_node("retrieval", retrieval_node))
    graph.add_node("plan", timed_node("plan", plan_node))
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


# One compiled graph per variant, built once at import. (B-Opus and C-Opus
# compile their own copies of B's and C's graphs: the models are in the state,
# not in the graph.)
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
    pillar: str | None = None,
    variant: str | None = None,
    models: dict[str, str] | None = None,
) -> dict:
    """Run the pipeline. Returns status "ok" with the post, status
    "low_coverage" (empty post, closest_sources, suggestion) when the coverage
    gate stops it before drafting, or status "draft_truncated" (empty post,
    message) when a single-writer draft was cut off at its output limit, or
    status "draft_refused" (empty post, message) when the draft model declined
    to write it, or "draft_empty" when a completed reply contains no usable
    post (recorded as empty_output). no_specifics=True skips the gate; it raises
    ValueError while config.features.NO_SPECIFICS_MODE_ENABLED is off.

    Under variant B an "ok" result carries review: {outcome, issues: [{type,
    sentence_text}]}, the acting issues on the returned post
    (pipeline.redraft); it is None when no review ran (A, C, and B with
    quality="draft"). Only variant A scores a post.

    STOPGAP: variant B's review summary is not shown by the frontend.
    Proper fix: feat/citations-ui exposes per-sentence citations and recorded
    check/review results; the author decides what to change. Refine alignment
    and explicit no-post statuses are implemented here.

    pillar: business users only, the key of the content pillar this post is
    (config.niches); it adds that pillar's lines to the draft prompt. A key the
    user's niche does not have is ignored here (/generate rejects it first).

    variant: which pipeline to run (config.features.PIPELINE_VARIANTS). None
    uses the configured one (PIPELINE_VARIANT, default D-Opus-low); evals pass it to
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
        "pillar": pillar,
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

    started = time.perf_counter()
    with trace_calls() as calls:
        result = PIPELINES[variant].invoke(initial_state)
        # The whole run, graph and model calls included; the trace write is not.
        result["run_seconds"] = round(time.perf_counter() - started, 3)
        # A's normal-mode fact check only marks itself pending, and nothing runs
        # it any more, so the pending record is dropped.
        if (result.get("fact_check") or {}).get("mode") == "log_only":
            result.pop("fact_check")

    # The trace is diagnostic only: a failed write must never fail generation.
    trace_id: str | None = None
    write_started = time.perf_counter()
    try:
        trace_id = save_generation_trace(build_trace_row(result, calls))
    except Exception:
        logger.exception("generation trace write failed for user %s", user_id)
    logger.info("generation run %.3fs, trace write %.3fs", result["run_seconds"], time.perf_counter() - write_started)

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
            "suggestion": ("Add " + result["business"]["pillar"]["needs"] + "."
                           if features.business_block_enabled() and (result.get("business") or {}).get("pillar") and not result["business"]["pillar"]["writable_from_profile"]
                           else LOW_COVERAGE_SUGGESTION),
            "trace_id": trace_id,
        }

    if result.get("draft_truncated") or result.get("draft_refused") or result.get("draft_empty"):
        refused = bool(result.get("draft_refused"))
        empty = bool(result.get("draft_empty"))
        return {
            "status": "draft_refused" if refused else "draft_empty" if empty else "draft_truncated",
            "post": "",
            "message": DRAFT_REFUSED_MESSAGE if refused else DRAFT_EMPTY_MESSAGE if empty else DRAFT_TRUNCATED_MESSAGE,
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
        "fact_check_job": None,
        "review": review_summary(result),
    }
