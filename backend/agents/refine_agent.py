"""Selection refine: rewrite one selected passage of a post, outside the pipeline.

The rewrite may change wording, structure and emphasis, never what the post
claims. New facts may only come from the post, the author's instruction or the
post's original sources (its generation trace). Numbers, dates, durations and
money are checked by the same specifics guard the pipeline's rewrite nodes use.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from llm.client import SONNET, complete
from memory.profile_store import load_profile, profile_to_context_string
from memory.trace_store import append_trace_guard_entry, get_trace_sources
from utils.specifics import GuardSources, find_violations, guard_entry, guard_sources, profile_facts, retry_note

logger = logging.getLogger(__name__)

REVERTED_MESSAGE = (
    "Couldn't refine without adding details that aren't in your sources. "
    "Try adding them to your instruction."
)
NO_TRACE_MESSAGE = (
    "This post has no saved sources, so the rewrite was checked against the post "
    "text and your profile only."
)
_NO_SOURCES_BLOCK = "(No saved sources for this post. Use only the post and the instruction.)"

REFINE_SELECTION_PROMPT = """You are editing one selected section of a post. You may change its wording, structure and emphasis. You may not change what it claims.

Author profile. Match this person's voice exactly:
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
class RefineSources:
    """What a selection rewrite may draw on, and where that came from."""
    origin: str            # "trace" | "post_and_profile"
    prompt_block: str      # the sources as shown to the model
    guard: GuardSources    # what the specifics guard accepts
    trace_id: str | None = None  # the trace the sources came from, if any


def load_refine_sources(
    full_post: str,
    instruction: str,
    profile: dict[str, Any],
    *,
    user_id: str,
    trace_id: str | None = None,
    post_id: int | None = None,
) -> RefineSources:
    """Sources for refining a post: its generation trace when the user has one
    (found by trace_id, else by post_id), otherwise the post and profile only.
    The post text, the instruction and the current profile always count."""
    always = [full_post, instruction, profile_facts(profile)]  # writing samples are style, not a source
    trace = get_trace_sources(user_id=user_id, trace_id=trace_id, post_id=post_id)
    if trace is None:
        return RefineSources("post_and_profile", _NO_SOURCES_BLOCK,
                             guard_sources({"profile": profile}, extra=always))

    no_specifics = bool((trace.get("node_outputs") or {}).get("no_specifics"))
    state = {
        "topic": trace.get("topic") or "",
        "context": trace.get("context") or "",
        "profile": trace.get("profile_snapshot") or {},
        "retrieval_bundle": {"chunks": trace.get("retrieved") or []},
        "no_specifics": no_specifics,
    }
    # An opinion post without specifics was written without its chunks; refining
    # it must not bring them in either.
    shown = "" if no_specifics else (trace.get("retrieved_context") or "").strip()
    return RefineSources("trace", shown or _NO_SOURCES_BLOCK, guard_sources(state, extra=always),
                         trace_id=str(trace["id"]))


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

    Returns {rewritten_text, status ("ok" | "reverted"), message, note,
    sources_used ("trace" | "post_and_profile"), sources_message}.
    """
    profile = load_profile(user_id)
    sources = load_refine_sources(full_post, instruction, profile,
                                  user_id=user_id, trace_id=trace_id, post_id=post_id)

    def rewrite(violations, event_type: str) -> tuple[str, str]:
        prompt = REFINE_SELECTION_PROMPT.format(
            profile_context=profile_to_context_string(profile),
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
        return _split_note(response.content[0].text)

    result = {
        "rewritten_text": selected_text,
        "status": "ok",
        "message": "",
        "note": "",
        "sources_used": sources.origin,
        "sources_message": "" if sources.origin == "trace" else NO_TRACE_MESSAGE,
    }

    rewritten, note = rewrite([], "refine_selection")
    first = find_violations(rewritten, sources.guard)
    if first:
        logger.info("refine_selection: first attempt added %s; retrying", [v.text for v in first])
        rewritten, note = rewrite(first, "refine_selection_retry")
        second = find_violations(rewritten, sources.guard)
        _record_guard_retry(sources, user_id, first, second)
        if second:
            logger.warning("refine_selection: retry still added %s; keeping the selection",
                           [v.text for v in second])
            return {**result, "status": "reverted", "message": REVERTED_MESSAGE}

    # A reply that is only a note leaves the selection as it was.
    return {**result, "rewritten_text": rewritten or selected_text, "note": note}
