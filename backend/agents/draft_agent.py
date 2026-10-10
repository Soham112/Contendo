"""The draft calls. The prompts are built in agents/draft_prompt.py.

draft_node is pipeline A's drafter: it picks the archetype, drafts, and runs
the specifics guard (one retry, then sentence removal).
structure_node and cited_draft_node are the single-writer drafter for variants
B and C: the archetype's structure is chosen first, then one draft call whose
output carries citation markers. No guard retry and no sentence removal run
there; what the draft got wrong is for the checks after it to find.
"""

import logging

from agents.archetype_agent import choose_archetype, choose_structure
from agents.draft_prompt import build_cited_prompt, build_prompt, format_retrieval_context
from llm.client import SONNET, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.specifics import find_violations, guard_entry, guard_sources, remove_sentences, retry_note

logger = logging.getLogger(__name__)

# Output budget for one draft call, in both pipelines.
_DRAFT_MAX_TOKENS = 2000


def _usage_metadata(state: PipelineState) -> dict[str, str]:
    return {
        "topic": state.get("topic", ""),
        "format": state.get("format", ""),
        "archetype": state.get("archetype", ""),
    }


def draft_node(state: PipelineState) -> PipelineState:
    # One Haiku call picks the archetype from the types the sources allow.
    decision = choose_archetype(state)
    state["archetype"] = decision["archetype"]
    state["archetype_decision"] = decision

    chunks_text = format_retrieval_context(state)
    prompt = build_prompt(state, chunks_text)
    state["draft_frame_block"] = chunks_text

    def write(violations, event_type: str) -> str:
        message = complete(
            model=SONNET,
            max_tokens=_DRAFT_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt + retry_note(
                violations, no_specifics=bool(state.get("no_specifics")), node="draft")}],
            user_id=state["user_id"],
            event_type=event_type,
            usage_metadata=_usage_metadata(state),
        )
        return message.content[0].text.strip()

    # Specifics guard: the draft may use only facts from the chunks, the profile,
    # the topic and the context, and first-person incidents only from
    # self-authored chunks. Retry once; then drop the sentences still at fault.
    sources = guard_sources(state)
    draft = write([], "generate")
    first = find_violations(draft, sources)
    if first:
        draft = write(first, "generate_retry")
        second = find_violations(draft, sources)
        state["specifics_guard"] = [*state.get("specifics_guard", []),
                                    guard_entry("draft", 0, first, second, fallback="sentences_removed")]
        if second:
            logger.warning("draft: retry still had %s; removing those sentences", [v.text for v in second])
            draft = remove_sentences(draft, second)

    state["current_draft"] = draft
    record_draft(state, "draft")

    return state


# ── Single writer (variants B and C) ──────────────────────────────────────────

def structure_node(state: PipelineState) -> PipelineState:
    """One Haiku call picks the post's structure from the types the sources
    allow. It names no event: for a story type the drafter does that."""
    decision = choose_structure(state)
    state["archetype"] = decision["archetype"]
    state["archetype_decision"] = decision
    return state


def cited_draft_node(state: PipelineState) -> PipelineState:
    """One Sonnet call writes the post with citation markers (and, for a story
    type, the EVENT line). The output is stored exactly as written: the markers
    are read and removed by the step after this one."""
    prompt, sources = build_cited_prompt(state)
    state["draft_frame_block"] = sources.text
    state["source_index"] = sources.index

    message = complete(
        model=SONNET,
        max_tokens=_DRAFT_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        user_id=state["user_id"],
        event_type="generate",
        usage_metadata=_usage_metadata(state),
    )
    state["current_draft"] = message.content[0].text.strip()
    record_draft(state, "draft")
    return state
