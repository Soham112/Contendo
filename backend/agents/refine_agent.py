"""Selection refine: rewrite one selected passage of a post, outside the pipeline.

The rewrite may change wording, structure and emphasis, never what the post
claims. New facts may only come from the author's instruction or the post's
original sources (its generation trace).

Which writer runs depends on how the post was made:
- A single-writer post (its trace stored a source index: variants B, C, B-Opus,
  C-Opus) is rewritten by the model that drafted it, from the same delimited
  sources block, with a citation marker on every sentence, and the passage goes
  through the deterministic checks (pipeline.checks.run_passage_checks). The
  prompt is in agents/refine_prompt.py.
- A post with no source index (pipeline A's, and posts from before the single
  writer) keeps the earlier writer: Sonnet, the frame-formatted sources, and the
  specifics guard on numbers, dates, durations and money.
Both retry once with what was found, and return the selection unchanged
(status "reverted") when the second attempt fails too.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from llm.client import REFUSAL, SONNET, complete, message_text
from llm.models import MODELS
from memory.profile_store import load_profile, profile_voice_context
from memory.trace_store import append_trace_guard_entry, get_trace_sources
from utils.formatters import normalise_post_punctuation
from utils.frames import format_chunks_by_frame, sources_block_from_index
from utils.specifics import GuardSources, find_violations, guard_entry, guard_sources, profile_facts, retry_note

logger = logging.getLogger(__name__)

REVERTED_MESSAGE = (
    "Couldn't refine without adding details that aren't in your sources. "
    "Try adding them to your instruction."
)
MISSING_SOURCES_MESSAGE = (
    "This post has no saved source tracking. Regenerate it to refine with sources."
)


class MissingRefineSources(RuntimeError):
    """A selection cannot be edited without its original structured sources."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(MISSING_SOURCES_MESSAGE)
        logger.warning("refine_selection: refine_sources_missing reason=%s", reason)


_NO_SOURCES_BLOCK = "(No saved sources for this post. Use only the post and the instruction.)"

# Output budget for the rewritten passage itself (a selection is a few
# sentences); a model that thinks gets room for that on top (llm.client.output_budget).
_REFINE_MAX_TOKENS = 500

REFINE_SELECTION_PROMPT = """You are editing one selected section of a post. You may change its wording, structure and emphasis. You may not change what it claims.

Author voice (voice and style only; never a source of content or angles):
{profile_context}

Words this person never uses: {words_to_avoid}

Never use the em dash character (—) anywhere in the output.

Full post (for voice and context only; do NOT rewrite it):
{full_post}

The post's original sources (what the author's knowledge base held when the post was written):
{sources_block}

Selected section to rewrite:
{selected_text}

Instruction from the author:
{instruction}

Where facts may come from:
- Every fact, number, date, name and event in your rewrite must already be in the selected section, the full post, the author's instruction or the original sources above.
- Never invent an example, anecdote, statistic, name, quote or event, and never write something that only sounds like it happened.
- Keep each source's attribution. Do not present something a source attributes to someone else as the author's own experience.
- If the instruction asks for something none of those contain (for example "add a real example" when no source has one), do not make it up. Make the part of the change you can, keep the section's facts as they are, and end your output with one short note on its own line, in exactly this form:
  <note>what you could not add, and what the author could put in the instruction so you can</note>
- Add a note only in that case.

Rules:
- Rewrite ONLY the selected section according to the instruction
- Match the voice, tone, and style of the surrounding post exactly
- Output ONLY the rewritten text (and the note, if one is needed): no explanation, no preamble, no quotes
- Do not add line breaks unless the original had them
- Keep roughly the same length unless the instruction says otherwise
- No em dashes anywhere in the output{specifics_retry}"""

# The optional trailing note; tolerate a missing closing tag.
_NOTE_RE = re.compile(r"<note>(.*?)(?:</note>|\Z)", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class CitedSources:
    """What a single-writer post's trace stored, for a cited rewrite."""
    source_index: dict[str, dict]   # S-id -> {position, chunk_id, frame, authorship}, as the drafter numbered them
    chunks: list[dict]              # the trace's stored chunks; an index entry's position points into this
    block: str                      # the delimited sources block, rebuilt from the two
    topic: str
    context: str
    model: str                      # the model that drafted the post, which rewrites it


@dataclass(frozen=True)
class RefineSources:
    """What a selection rewrite may draw on, and where that came from."""
    origin: str            # "trace"; missing tracking raises MissingRefineSources
    prompt_block: str      # the sources as shown to the model
    guard: GuardSources    # what the specifics guard accepts
    trace_id: str | None = None  # the trace the sources came from, if any
    cited: CitedSources | None = None   # set for a single-writer post; None keeps the earlier writer


def load_refine_sources(
    full_post: str,
    instruction: str,
    profile: dict[str, Any],
    *,
    user_id: str,
    trace_id: str | None = None,
    post_id: int | None = None,
) -> RefineSources:
    """Sources from the user's trace; unavailable tracking fails explicitly.
    The post, instruction and non-sample profile facts also support the guard."""
    if not trace_id and post_id is None:
        raise MissingRefineSources("no_identifier")
    always = [full_post, instruction, profile_facts(profile)]  # writing samples are style, not a source
    trace = get_trace_sources(user_id=user_id, trace_id=trace_id, post_id=post_id)
    if trace is None:
        raise MissingRefineSources("trace_not_found")
    chunks = trace.get("retrieved")
    if (not isinstance(chunks, list) or not chunks
            or any(not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str)
                   or not chunk["text"].strip() for chunk in chunks)):
        raise MissingRefineSources("structured_chunks_missing")

    no_specifics = bool((trace.get("node_outputs") or {}).get("no_specifics"))
    state = {
        "topic": trace.get("topic") or "",
        "context": trace.get("context") or "",
        "profile": trace.get("profile_snapshot") or {},
        "retrieval_bundle": {"chunks": chunks},
        "no_specifics": no_specifics,
    }
    # An opinion post without specifics was written without its chunks; refining
    # it must not bring them in either.
    shown = "" if no_specifics else format_chunks_by_frame(chunks, state["profile"])
    return RefineSources("trace", shown or _NO_SOURCES_BLOCK, guard_sources(state, extra=always),
                         trace_id=str(trace["id"]), cited=_cited_sources(trace, chunks))


def _cited_sources(trace: dict[str, Any], chunks: list[dict]) -> CitedSources | None:
    """The stored source index and what goes with it, when the trace has one.
    The S-ids are the ones the drafter used, resolved through the stored index
    to the stored chunks; they are never rebuilt from retrieval order. An index
    that points outside the stored chunks is a broken trace: MissingRefineSources."""
    outputs = trace.get("node_outputs") or {}
    source_index = outputs.get("source_index")
    if not source_index:
        return None
    try:
        block = sources_block_from_index(source_index, chunks)
    except (ValueError, KeyError, TypeError):
        raise MissingRefineSources("source_index_does_not_match_chunks") from None
    drafted_by = (outputs.get("models") or {}).get("draft")
    if not drafted_by:
        raise MissingRefineSources("draft_model_missing")
    if drafted_by not in MODELS:
        raise MissingRefineSources("draft_model_unknown")
    model = drafted_by
    return CitedSources(source_index, chunks, block, trace.get("topic") or "", trace.get("context") or "", model)


def _record_guard_retry(sources: RefineSources, user_id: str, first: list, second: list) -> None:
    """Add the retry to the trace's specifics_guard list so evals can see it.
    Without a trace the log lines are the record. Never fails the request."""
    if sources.trace_id is None:
        return
    try:
        append_trace_guard_entry(sources.trace_id, user_id,
                                 guard_entry("refine_selection", 0, first, second))
    except Exception:
        logger.exception("refine_selection: recording the guard result on trace %s failed", sources.trace_id)


def _split_note(raw: str) -> tuple[str, str]:
    """(rewritten text, note). The note is "" when the model added none."""
    notes = [m.strip() for m in _NOTE_RE.findall(raw) if m.strip()]
    return _NOTE_RE.sub("", raw).strip(), " ".join(notes)


REFUSED_MESSAGE = "The model declined to rewrite this selection. Try different wording in your instruction."
TRUNCATED_MESSAGE = "The rewrite was cut off before it finished. Try a shorter selection."
EMPTY_REFINE_MESSAGE = "The model returned no rewrite after two attempts. Your selection was kept. Try again."



def refine_selection(
    selected_text: str,
    instruction: str,
    full_post: str,
    *,
    user_id: str,
    trace_id: str | None = None,
    post_id: int | None = None,
) -> dict[str, Any]:
    """Rewrite only the selected fragment, without adding unsupported specifics.

    If the rewrite adds a number, date, duration or money amount that no source
    supports, retry once with the violations listed; if the retry still does,
    return the selection unchanged with status "reverted". A retry is recorded
    in the trace's specifics_guard list (node "refine_selection") when the post
    has a trace.

    A single-writer post takes the cited rewrite instead (agents.refine_cited_agent.refine_cited): the
    same contract, with the deterministic checks in place of the guard.

    Returns {rewritten_text, status ("ok" | "reverted"), message, note,
    sources_used ("trace" | "post_and_profile"), sources_message}.
    """
    profile = load_profile(user_id)
    sources = load_refine_sources(full_post, instruction, profile,
                                  user_id=user_id, trace_id=trace_id, post_id=post_id)
    if sources.cited is not None:
        from agents.refine_cited_agent import refine_cited
        return refine_cited(selected_text, instruction, full_post, profile, sources, user_id)

    def rewrite(violations, event_type: str) -> tuple[str, str, str | None]:
        prompt = REFINE_SELECTION_PROMPT.format(
            profile_context=profile_voice_context(profile),
            words_to_avoid=", ".join(profile.get("words_to_avoid", [])),
            full_post=full_post,
            sources_block=sources.prompt_block,
            selected_text=selected_text,
            instruction=instruction,
            specifics_retry=retry_note(violations, node="selection"),
        )
        response = complete(
            model=SONNET,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            event_type=event_type,
        )
        unusable = {REFUSAL: REFUSED_MESSAGE, "max_tokens": TRUNCATED_MESSAGE}.get(response.stop_reason)
        text, note = _split_note(message_text(response))
        return text, note, unusable

    result = {
        "rewritten_text": selected_text,
        "status": "ok",
        "message": "",
        "note": "",
        "sources_used": sources.origin,
        "sources_message": "",
    }

    rewritten, note, unusable = rewrite([], "refine_selection")
    if unusable:
        return {**result, "status": "reverted", "message": unusable}
    first = find_violations(rewritten, sources.guard)
    if first:
        logger.info("refine_selection: first attempt added %s; retrying", [v.text for v in first])
        rewritten, note, unusable = rewrite(first, "refine_selection_retry")
        if unusable:
            return {**result, "status": "reverted", "message": unusable}
        second = find_violations(rewritten, sources.guard)
        _record_guard_retry(sources, user_id, first, second)
        if second:
            logger.warning("refine_selection: retry still added %s; keeping the selection",
                           [v.text for v in second])
            return {**result, "status": "reverted", "message": REVERTED_MESSAGE}

    # A reply that is only a note leaves the selection as it was.
    return {**result, "rewritten_text": normalise_post_punctuation(rewritten) if rewritten else selected_text, "note": note}
