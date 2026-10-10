"""Finalise: the last thing that happens to a post's text, and the record of it.

finalise() is the one function that turns text into the text a user may see:
it normalises punctuation (em dashes, with code, URLs and quoted literals left
alone) and then measures and checks exactly the string it returns. It runs
after every step that changes a post's content, so the post that is returned is
always the last string that was validated. validation_record() is the check on
its own, for a pipeline whose text must not be touched here (pipeline A, which
normalises in its own finalize step and is recorded only).

The record:
    words                 the post's length: prose_word_count() for variants B and C
                          (headings, placeholder lines and code blocks are not
                          counted), count_words() for pipeline A (every token)
    target                {min_words, max_words, basis} or None (threads)
    length                "ok" | "over_length" | "under_length" | "no_target"
    over_by, under_by     words beyond the maximum / short of the minimum (0 when not)
    leftover_markers      citation-marker-like text still in the post
    em_dashes_remaining   em dashes left outside code, URLs and quoted literals

An under-length post is recorded and nothing else: no step lengthens a post.

The single-writer nodes that apply this (variants B and C) are here too:
strip_draft_node, finalise_draft_node, finalise_trimmed_node, truncated_node,
and settle(), which the code-made edits of variant B use (pipeline/fixes.py).
"""

import logging
from dataclasses import dataclass
from typing import Any

from pipeline.state import PipelineState
from utils.citations import StrippedPost, leftover_markers, prose_word_count, strip_citations
from utils.draft_output import parse_draft_output
from utils.sentences import multi_sentence_span_count
from utils.formatters import GENERAL_ARCHETYPE, STORY_ARCHETYPES, count_words, normalise_post_punctuation
from utils.text_spans import protected_spans

logger = logging.getLogger(__name__)

EM_DASH = "—"


@dataclass(frozen=True)
class Finalised:
    text: str                  # the validated text: what may be returned
    record: dict[str, Any]     # the validation record for exactly that text


def _prose_em_dashes(text: str) -> int:
    """Em dashes outside the spans the normaliser leaves alone."""
    count, cursor = 0, 0
    for start, end in protected_spans(text):
        count += text[cursor:start].count(EM_DASH)
        cursor = end
    return count + text[cursor:].count(EM_DASH)


def validation_record(text: str, target: dict[str, Any] | None, count=count_words) -> dict[str, Any]:
    """Measure and check text as it stands. Changes nothing. count is how the
    post's length is measured: count_words (pipeline A, the default) or
    utils.citations.prose_word_count (variants B and C)."""
    words = count(text)
    over_by = under_by = 0
    if target is None:
        length = "no_target"
    else:
        over_by = max(0, words - target["max_words"])
        under_by = max(0, target["min_words"] - words)
        length = "over_length" if over_by else "under_length" if under_by else "ok"
    return {
        "words": words,
        "target": None if target is None else {k: target[k] for k in ("min_words", "max_words", "basis")},
        "length": length,
        "over_by": over_by,
        "under_by": under_by,
        "leftover_markers": [{"kind": m.kind, "text": m.text, "start": m.start, "end": m.end}
                             for m in leftover_markers(text)],
        "em_dashes_remaining": _prose_em_dashes(text),
    }


def finalise(text: str, target: dict[str, Any] | None) -> Finalised:
    """Normalise a single-writer post and validate the result. Its length is
    its prose (prose_word_count)."""
    final = normalise_post_punctuation(text)
    return Finalised(final, validation_record(final, target, prose_word_count))


def finalise_marked(marked: str, target: dict[str, Any] | None) -> tuple[Finalised, StrippedPost]:
    """finalise() for a draft that still has its citation markers.

    The punctuation is normalised before the markers are removed, so the spans'
    offsets are offsets into the text that is returned. The record is of that
    text, after both.
    """
    stripped = strip_citations(normalise_post_punctuation(marked))
    return Finalised(stripped.text, validation_record(stripped.text, target, prose_word_count)), stripped


# ── Single-writer nodes (variants B and C) ────────────────────────────────────

def strip_draft_node(state: PipelineState) -> PipelineState:
    """Read the draft's envelope: keep what is inside <post>, read the <event>
    part, and drop everything else. The markers stay for finalise_draft_node.

    Records what the <event> part said (event) and anything that broke the
    envelope (draft_format: [{draft, kind, text}], one entry per failure, where
    draft is the draft_history node that wrote it). When the drafter answered
    <event>none</event> it wrote to the General structure, so the archetype
    becomes General and the decision says why. A failed event is recorded, not
    acted on here.
    """
    chosen = state.get("archetype", "")
    output = parse_draft_output(state.get("current_draft", ""), story=chosen in STORY_ARCHETYPES)
    state["event"] = {"status": output.status, "source": output.source,
                      "quote": output.quote, "line": output.line}
    if output.format_failures:
        history = state.get("draft_history") or [{}]
        logger.warning("strip: draft format failures: %s", [f["kind"] for f in output.format_failures])
        state["draft_format"] = [*state.get("draft_format", []),
                                 *({"draft": history[-1].get("node", ""), **f} for f in output.format_failures)]
    if output.status == "none":
        state["archetype"] = GENERAL_ARCHETYPE
        state["archetype_decision"] = {
            **(state.get("archetype_decision") or {}),
            "archetype": GENERAL_ARCHETYPE, "downgraded_from": chosen,
            "reason": "the drafter found no event that fits the topic",
        }
    if output.failed:
        logger.warning("strip: event %s", output.status)
    state["current_draft"] = output.body
    return state


def finalise_draft_node(state: PipelineState) -> PipelineState:
    """Finalise the marked draft: normalise, remove the markers, validate.

    Sets the post (current_draft, final_post), its spans (citations), marker
    failures (citation_failures) and the validation record (final_validation).
    Also counts the spans that hold more than one sentence
    (multi_sentence_spans): a measure of citation compliance that is recorded
    and triggers nothing.
    """
    finalised, stripped = finalise_marked(state.get("current_draft", ""), state.get("length_target"))
    state["citations"] = [span.as_dict() for span in stripped.spans]
    state["multi_sentence_spans"] = multi_sentence_span_count(stripped.spans)
    state["citation_failures"] = [
        {"kind": f.kind, "text": f.text, "start": f.start, "end": f.end} for f in stripped.failures
    ]
    if stripped.failures:
        logger.warning("finalise: %d marker failure(s) in the draft", len(stripped.failures))
    state["current_draft"] = state["final_post"] = finalised.text
    state["final_validation"] = finalised.record
    return state


def finalise_trimmed_node(state: PipelineState) -> PipelineState:
    """Finalise the post again after the trim changed it.

    A trim only deletes spans, so normalising should change nothing. If it does,
    the spans' offsets no longer match the text: that is recorded
    (final_validation.spans_stale), never passed over.
    """
    before = state.get("current_draft", "")
    finalised = finalise(before, state.get("length_target"))
    record = finalised.record
    if finalised.text != before:
        logger.warning("finalise: normalising changed the trimmed post; span offsets are stale")
        record = {**record, "spans_stale": True}
    state["current_draft"] = state["final_post"] = finalised.text
    state["final_validation"] = record
    return state


def settle(state: PipelineState, text: str, spans) -> None:
    """Make an edited post (text and its spans, after a deletion or a
    replacement made in code) the post in state, finalised: the same record
    finalise_trimmed_node keeps after a trim."""
    state["current_draft"] = text
    state["citations"] = [span.as_dict() for span in spans]
    finalise_trimmed_node(state)


def truncated_node(state: PipelineState) -> PipelineState:
    """A draft that hit its output limit, or that the model declined to write,
    is not a post: return none."""
    state["final_post"] = ""
    return state


def route_after_cited_draft(state: PipelineState) -> str:
    return "truncated" if state.get("draft_truncated") or state.get("draft_refused") else "strip"


def route_to_trim(state: PipelineState) -> str:
    """Trim only a post that is over its maximum. Under-length ends here."""
    return "trim" if (state.get("final_validation") or {}).get("length") == "over_length" else "end"
