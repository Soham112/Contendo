"""Graph wiring for the single-writer variants, after the shared plan step.

C (draft only): structure → draft → strip → finalise → checks → trim (only
when over the maximum) → finalise → checks again → end. The checks are recorded
and nothing acts on them.

B (reviewed): the same first draft, then review → decide. With no acting issue
it ends there. Otherwise code_fix makes the fixes that need no model and
chooses one path for what is left (pipeline/fixes.py):
  none      → review_fixed
  targeted  → targeted_fix (one drafter call, replacements for the flagged
              sentences only) → review_fixed
  full      → redraft (one drafter call, the whole post) → strip → finalise →
              checks → review_redraft → code_fix_redraft (the code fixes
              again, on the redraft) → review_refixed (no call)
then trim (only when over the maximum) → finalise → checks again → outcome.
No edge joins the targeted and the full path, and none leads back to a
drafting step, so a run makes at most one of those calls and never a third
draft. A full redraft cut off at its output limit leaves the post as the code
fixes made it, which goes on through review_fixed.
With quality="draft" B takes C's path after the first checks: no review and no
fix. quality="polished" is the same as "standard".

In both, a first draft cut off at its output limit goes straight to
"truncated" and the run returns no post. "structure" is the archetype choice
(structure only; "archetype" is a state key, so the node cannot have that name;
"review_draft" is the first review for the same reason).

Every B step records how long it took (state["step_timings"]).
"""

import time
from typing import Callable

from langgraph.graph import END, StateGraph

from agents.archetype_agent import structure_node
from agents.draft_agent import cited_draft_node, redraft_node, targeted_fix_node
from agents.review_agent import review_fixed_node, review_node, review_redraft_node, review_refixed_node
from agents.trim_agent import trim_node
from pipeline.checks import checks_node, recheck_node
from pipeline.finalise import (
    finalise_draft_node, finalise_trimmed_node, route_after_cited_draft, route_to_trim,
    strip_draft_node, truncated_node,
)
from pipeline.fixes import code_fix_node, code_fix_redraft_node, route_after_fix
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
    """A full redraft goes through its own second pass. A cut-off one left the
    post as the code fixes made it, which is reviewed as that."""
    return "kept" if "redraft_truncated" in state["review"] else "strip"


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
    add("code_fix", code_fix_node)
    add("targeted_fix", targeted_fix_node)
    add("review_fixed", review_fixed_node)
    add("redraft", redraft_node)
    add("strip_redraft", strip_draft_node)
    add("finalise_redraft", finalise_draft_node)
    add("checks_redraft", checks_node)
    add("review_redraft", review_redraft_node)
    add("code_fix_redraft", code_fix_redraft_node)
    add("review_refixed", review_refixed_node)
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
    graph.add_conditional_edges("decide", route_after_decide, {"fix": "code_fix", "outcome": "outcome"})
    graph.add_conditional_edges("code_fix", route_after_fix,
                                {"none": "review_fixed", "targeted": "targeted_fix", "full": "redraft"})
    graph.add_edge("targeted_fix", "review_fixed")
    graph.add_conditional_edges("review_fixed", route_to_trim, {"trim": "trim", "end": "outcome"})
    graph.add_conditional_edges("redraft", route_after_redraft, {"strip": "strip_redraft", "kept": "review_fixed"})
    graph.add_edge("strip_redraft", "finalise_redraft")
    graph.add_edge("finalise_redraft", "checks_redraft")
    graph.add_edge("checks_redraft", "review_redraft")
    graph.add_edge("review_redraft", "code_fix_redraft")
    graph.add_edge("code_fix_redraft", "review_refixed")
    graph.add_conditional_edges("review_refixed", route_to_trim, {"trim": "trim", "end": "outcome"})
    graph.add_edge("trim", "finalise_trimmed")
    graph.add_edge("finalise_trimmed", "recheck")
    graph.add_edge("recheck", "outcome")
    graph.add_edge("outcome", END)
