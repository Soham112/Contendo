"""The draft calls. The prompts are built in agents/draft_prompt.py.

draft_node is pipeline A's drafter: it picks the archetype, drafts, and runs
the specifics guard (one retry, then sentence removal).
cited_draft_node is the single-writer drafter for variants B and C: after the
structure is chosen (agents/archetype_agent.structure_node), one draft call
whose output carries citation markers. No guard retry and no sentence removal run
there; what the draft got wrong is for the checks after it to find.
targeted_fix_node and redraft_node are variant B's two ways of having the
drafter deal with the problems the checks and the review found, of which a run
takes at most one (pipeline/fixes.py chooses): replacements for the flagged
sentences only, or the whole post again.
"""

import logging

from agents.archetype_agent import choose_archetype
from agents.draft_prompt import build_cited_prompt, build_prompt, format_retrieval_context
from agents.redraft_prompt import build_fix_prompt, build_redraft_prompt
from llm.client import SONNET, complete
from pipeline.fixes import apply_targeted_fixes
from pipeline.redraft import apply_downgrade
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.citations import Span, with_markers
from utils.formatters import draft_max_tokens
from utils.sentences import split_spans
from utils.specifics import find_violations, guard_entry, guard_sources, remove_sentences, retry_note

logger = logging.getLogger(__name__)

# Output budget for pipeline A's draft call. The single-writer draft takes its
# budget from the length target (utils.formatters.draft_max_tokens).
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

def cited_draft_node(state: PipelineState) -> PipelineState:
    """One Sonnet call writes the post with citation markers, inside its output
    envelope (<post>, and <event> for a story type). The output is stored
    exactly as written: the envelope and the markers are read and removed by
    the steps after this one.

    A draft that stops at its output limit is not a finished post. It is kept
    in draft_history for diagnosis and flagged in state["draft_truncated"]
    ({max_tokens, output_tokens}); the pipeline then returns no post."""
    prompt, sources = build_cited_prompt(state)
    state["draft_frame_block"] = sources.text
    state["source_index"] = sources.index

    max_tokens = draft_max_tokens(state.get("length_target"))
    message = complete(
        model=SONNET,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        user_id=state["user_id"],
        event_type="generate",
        usage_metadata=_usage_metadata(state),
    )
    state["current_draft"] = message.content[0].text.strip()
    record_draft(state, "draft")
    if message.stop_reason == "max_tokens":
        logger.warning("draft: cut off at max_tokens=%d; no post will be returned", max_tokens)
        state["draft_truncated"] = {"max_tokens": max_tokens, "output_tokens": message.usage.output_tokens}
    return state


def targeted_fix_node(state: PipelineState) -> PipelineState:
    """Variant B's targeted fix: one Sonnet call with the draft prompt, the post
    as numbered sentences and the problems in state["review"]["targeted"]. Its
    answer is a list of replacements for the flagged sentences; code validates
    and splices them (pipeline.fixes.apply_targeted_fixes), so no other
    sentence can change. An answer cut off at its output limit is not used."""
    prompt, _ = build_cited_prompt(state)
    targeted = state["review"]["targeted"]
    sentences = [sentence for _, sentence in split_spans([Span.from_dict(c) for c in state["citations"]])]
    message = complete(
        model=SONNET,
        max_tokens=draft_max_tokens(state.get("length_target")),
        messages=[{"role": "user", "content": build_fix_prompt(prompt, sentences, targeted["entries"])}],
        user_id=state["user_id"],
        event_type="targeted_fix",
        usage_metadata=_usage_metadata(state),
    )
    answer = message.content[0].text.strip()
    targeted.update(answer=answer, input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens)
    apply_targeted_fixes(state, answer, truncated=message.stop_reason == "max_tokens")
    if targeted["applied"]:
        record_draft(state, "targeted_fix")
    return state


def redraft_node(state: PipelineState) -> PipelineState:
    """Variant B's one full redraft, for a problem with the post's structure or
    length: one Sonnet call with the draft prompt, the post as the code fixes
    left it (with its markers) and the problems in
    state["review"]["redraft"]["entries"]. The prompt is rebuilt from state, so
    it is the first draft's prompt unless the structure became General since.
    The output replaces the draft and goes through the same steps the first one did.

    A redraft cut off at its output limit is not a post, and the post is not
    thrown away for it: the state is left as it was,
    state["review"]["redraft_truncated"] records {max_tokens, output_tokens},
    and the cut-off text is kept in draft_history for diagnosis only."""
    before = (state.get("archetype", ""), state.get("archetype_decision"))
    apply_downgrade(state)
    prompt, _ = build_cited_prompt(state)
    redraft = state["review"]["redraft"]
    previous = with_markers(state["current_draft"], [Span.from_dict(c) for c in state["citations"]])
    max_tokens = draft_max_tokens(state.get("length_target"))
    message = complete(
        model=SONNET,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": build_redraft_prompt(prompt, previous, redraft["entries"])}],
        user_id=state["user_id"],
        event_type="redraft",
        usage_metadata=_usage_metadata(state),
    )
    redraft["input_tokens"] = message.usage.input_tokens
    redraft["output_tokens"] = message.usage.output_tokens
    written = message.content[0].text.strip()
    if message.stop_reason == "max_tokens":
        logger.warning("redraft: cut off at max_tokens=%d; the post is returned as it was", max_tokens)
        state["review"]["redraft_truncated"] = {"max_tokens": max_tokens, "output_tokens": message.usage.output_tokens}
        state["draft_history"] = [*state["draft_history"], {
            "node": "redraft_truncated", "iteration": state.get("iterations", 0), "text": written}]
        state["archetype"], state["archetype_decision"] = before
        return state
    state["current_draft"] = written
    record_draft(state, "redraft")
    return state
