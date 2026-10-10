"""Graph wiring for the single-writer variants, after the shared plan step.

C (draft only): structure → draft → strip → finalise → checks → trim (only
when over the maximum) → finalise → checks again → end. The checks are recorded
and nothing acts on them.

B (reviewed): the same first draft, then review → decide → [redraft → strip →
finalise → checks → review of the changed sentences] → trim (only when over the
maximum) → finalise → checks again → outcome → end. The second pass has its own
nodes and no edge leads back to the redraft, so a third draft cannot happen.
With quality="draft" B takes C's path after the first checks: no review and no
redraft. quality="polished" is the same as "standard".

In both, a first draft cut off at its output limit goes straight to
"truncated" and the run returns no post. A cut-off redraft (B) is dropped and
the first draft goes on to the trim and the outcome as it stands. "structure" is the archetype choice (structure only;
"archetype" is a state key, so the node cannot have that name; "review_draft"
is the first review for the same reason).

Every B step records how long it took (state["step_timings"]).
"""

import time
from typing import Callable

from langgraph.graph import END, StateGraph

from agents.archetype_agent import structure_node
from agents.draft_agent import cited_draft_node, redraft_node
from agents.review_agent import review_node, review_redraft_node
from agents.trim_agent import trim_node
from pipeline.checks import checks_node, recheck_node
from pipeline.finalise import (
    finalise_draft_node, finalise_trimmed_node, route_after_cited_draft, route_to_trim,
    strip_draft_node, truncated_node,
)
from pipeline.redraft import decide_node, outcome_node, route_after_decide
from pipeline.state import PipelineState

Node = Callable[[PipelineState], PipelineState]


def wire_draft_only(graph: StateGraph) -> None:
    """Variant C."""
    graph.add_node("structure", structure_node)
    graph.add_node("draft", cited_draft_node)
    graph.add_node("truncated", truncated_node)
    graph.add_node("strip", strip_draft_node)
    graph.add_node("finalise", finalise_draft_node)
    graph.add_node("checks", checks_node)
    graph.add_node("trim", trim_node)
    graph.add_node("finalise_trimmed", finalise_trimmed_node)
    graph.add_node("recheck", recheck_node)

    graph.add_edge("plan", "structure")
    graph.add_edge("structure", "draft")
    graph.add_conditional_edges("draft", route_after_cited_draft, {"truncated": "truncated", "strip": "strip"})
    graph.add_edge("truncated", END)
    graph.add_edge("strip", "finalise")
    graph.add_edge("finalise", "checks")
    graph.add_conditional_edges("checks", route_to_trim, {"trim": "trim", "end": END})
    graph.add_edge("trim", "finalise_trimmed")
    graph.add_edge("finalise_trimmed", "recheck")
    graph.add_edge("recheck", END)


def _timed(step: str, node: Node) -> Node:
    """node, with its wall time appended to state["step_timings"] as {step, seconds}."""
    def run(state: PipelineState) -> PipelineState:
        started = time.perf_counter()
        result = node(state)
        result["step_timings"] = [*result.get("step_timings", []),
                                  {"step": step, "seconds": round(time.perf_counter() - started, 3)}]
        return result
    return run


def route_after_checks(state: PipelineState) -> str:
    """After the first draft's checks: quality="draft" is not reviewed and goes
    on as variant C does; every other quality is reviewed."""
    if state.get("quality", "standard") == "draft":
        return route_to_trim(state)
    return "review"


def route_after_redraft(state: PipelineState) -> str:
    """A redraft goes through the second pass. A cut-off one left the first
    draft in place, which goes on as a draft with no redraft would."""
    if "redraft_truncated" in state["review"]:
        return route_to_trim(state)
    return "strip"


def wire_reviewed(graph: StateGraph) -> None:
    """Variant B."""
    def add(step: str, node: Node) -> None:
        graph.add_node(step, _timed(step, node))

    add("structure", structure_node)
    add("draft", cited_draft_node)
    add("truncated", truncated_node)
    add("strip", strip_draft_node)
    add("finalise", finalise_draft_node)
    add("checks", checks_node)
    add("review_draft", review_node)
    add("decide", decide_node)
    add("redraft", redraft_node)
    add("strip_redraft", strip_draft_node)
    add("finalise_redraft", finalise_draft_node)
    add("checks_redraft", checks_node)
    add("review_redraft", review_redraft_node)
    add("trim", trim_node)
    add("finalise_trimmed", finalise_trimmed_node)
    add("recheck", recheck_node)
    add("outcome", outcome_node)

    graph.add_edge("plan", "structure")
    graph.add_edge("structure", "draft")
    graph.add_conditional_edges("draft", route_after_cited_draft, {"truncated": "truncated", "strip": "strip"})
    graph.add_edge("truncated", END)
    graph.add_edge("strip", "finalise")
    graph.add_edge("finalise", "checks")
    graph.add_conditional_edges("checks", route_after_checks, {"review": "review_draft", "trim": "trim", "end": END})
    graph.add_edge("review_draft", "decide")
    graph.add_conditional_edges("decide", route_after_decide, {"redraft": "redraft", "outcome": "outcome"})
    graph.add_conditional_edges("redraft", route_after_redraft,
                                {"strip": "strip_redraft", "trim": "trim", "end": "outcome"})
    graph.add_edge("strip_redraft", "finalise_redraft")
    graph.add_edge("finalise_redraft", "checks_redraft")
    graph.add_edge("checks_redraft", "review_redraft")
    graph.add_conditional_edges("review_redraft", route_to_trim, {"trim": "trim", "end": "outcome"})
    graph.add_edge("trim", "finalise_trimmed")
    graph.add_edge("finalise_trimmed", "recheck")
    graph.add_edge("recheck", "outcome")
    graph.add_edge("outcome", END)
