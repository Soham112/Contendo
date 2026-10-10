import logging
from typing import Callable

from langgraph.graph import StateGraph, END

from config import features
from llm.client import trace_calls
from pipeline.state import PipelineState
from pipeline.trace import build_trace_row
from utils.citations import parse_event_header, strip_citations
from utils.formatters import GENERAL_ARCHETYPE, STORY_ARCHETYPES, normalise_post_punctuation, resolve_length_target
from utils.frames import decide_perspective
from memory.profile_store import load_profile
from memory.feedback_store import get_all_topics_posted
from memory.trace_store import save_generation_trace
from agents.retrieval_agent import retrieval_node
from agents.draft_agent import cited_draft_node, draft_node, structure_node
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
    return state


def strip_draft_node(state: PipelineState) -> PipelineState:
    """Single writer: turn the marked draft into the post the user sees.

    Reads and removes the EVENT line and the citation markers, and records what
    they said (event, citations) and anything wrong with them
    (citation_failures). When the drafter answered "EVENT: none" it wrote to the
    General structure, so the archetype becomes General and the decision says why.
    """
    chosen = state.get("archetype", "")
    header = parse_event_header(state.get("current_draft", ""), required=chosen in STORY_ARCHETYPES)
    stripped = strip_citations(header.body)

    state["event"] = {"status": header.status, "source": header.source,
                      "quote": header.quote, "line": header.line}
    state["citations"] = [
        {"start": s.start, "end": s.end, "text": s.text, "basis": s.basis, "sources": list(s.sources)}
        for s in stripped.spans
    ]
    state["citation_failures"] = [
        {"kind": f.kind, "text": f.text, "start": f.start, "end": f.end} for f in stripped.failures
    ]
    if header.status == "none":
        state["archetype"] = GENERAL_ARCHETYPE
        state["archetype_decision"] = {
            **(state.get("archetype_decision") or {}),
            "archetype": GENERAL_ARCHETYPE, "downgraded_from": chosen,
            "reason": "the drafter found no event that fits the topic",
        }
    if header.failed or stripped.failures:
        logger.warning("strip: event header %s, %d marker failure(s)", header.status, len(stripped.failures))

    state["current_draft"] = stripped.text
    state["final_post"] = stripped.text
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


def _wire_cited_draft(graph: StateGraph) -> None:
    """Variants B and C, after plan: structure (the archetype, structure only;
    "archetype" is a state key, so the node cannot have that name) → draft (with
    citation markers) → strip (markers and EVENT line removed) → end.

    STOPGAP: B and C are the same pipeline and both stop after the draft. The
    post is returned without finalise (punctuation normalisation, final
    validation) or a length trim, `quality` is ignored, and nothing acts on
    citation_failures or a failed EVENT line: they are only recorded.
    Proper fix: finalise and trim-by-deletion for both (step 4 of the
    feat/single-writer plan); deterministic checks, the structured review and
    at most one redraft for B (steps 5-6).
    """
    graph.add_node("structure", structure_node)
    graph.add_node("draft", cited_draft_node)
    graph.add_node("strip", strip_draft_node)

    graph.add_edge("plan", "structure")
    graph.add_edge("structure", "draft")
    graph.add_edge("draft", "strip")
    graph.add_edge("strip", END)


# What runs after plan, per variant (config.features.PIPELINE_VARIANTS).
# Everything up to and including plan is shared.
_AFTER_PLAN: dict[str, Callable[[StateGraph], None]] = {
    "A": _wire_rewrite_chain,
    "B": _wire_cited_draft,
    "C": _wire_cited_draft,
}


def build_graph(variant: str):
    """The compiled pipeline for one variant: the shared nodes up to plan, then
    that variant's steps. Raises PipelineConfigError for an unknown variant."""
    wire_after_plan = _AFTER_PLAN[features.validate_pipeline_variant(variant)]
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


# One compiled graph per variant, built once at import.
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
) -> dict:
    """Run the pipeline. Returns status "ok" with the post, or status
    "low_coverage" (empty post, closest_sources, suggestion) when the coverage
    gate stops it before drafting. no_specifics=True skips the gate; it raises
    ValueError while config.features.NO_SPECIFICS_MODE_ENABLED is off.

    variant: which pipeline to run (config.features.PIPELINE_VARIANTS). None
    uses the configured one (PIPELINE_VARIANT, default A); evals pass it to
    compare variants. An unknown variant raises PipelineConfigError."""
    if no_specifics and not features.NO_SPECIFICS_MODE_ENABLED:
        raise ValueError("no-specifics mode is disabled (config.features.NO_SPECIFICS_MODE_ENABLED)")
    variant = features.pipeline_variant() if variant is None else features.validate_pipeline_variant(variant)
    initial_state: PipelineState = {
        "topic": topic,
        "format": format,
        "tone": tone,
        "length": length,
        "context": context,
        "quality": quality,
        "user_id": user_id,
        "variant": variant,
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

    return {
        "status": "ok",
        "post": result.get("final_post", result.get("current_draft", "")),
        "score": result.get("score", 0),
        "score_feedback": result.get("score_feedback", []),
        "iterations": result.get("iterations", 1),
        "archetype": result.get("archetype", ""),
        "scored": quality == "polished" and not result.get("score_error"),
        "retrieval_confidence": result.get("retrieval_confidence", "medium"),
        "trace_id": trace_id,
        "fact_check_job": fact_check_job,
    }
