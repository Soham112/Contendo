"""Deterministic checks on a single-writer post (variants B and C). No model calls.

Each check looks for one thing code can decide exactly, and returns issues:

    {type, span, text, sources, detail}

    type      the check's name (ISSUE_TYPES)
    span      position of the span in the post's spans, or None when the issue
              is not about one span (the EVENT line, the post's length, a marker
              or a heading outside any span)
    text      the span's text, or the text the issue is about
    sources   the source ids involved
    detail    a small dict, different per type, that says exactly what was found

What these checks cannot decide is meaning: whether a source really supports a
claim, whether an event fits the topic, whether a sentence marked as a view
states a fact in words. That is for the structured review.

Numbers, dates and durations are matched as utils.specifics matches them: number
words and digit formats are the same number ("nine" = "9", "410k" = "410,000",
"4 percent" = "4%"), and a bare number may restate a figure ("26" for "26%").
Nothing that needs judging is treated as equal: "a third" is not "33 percent",
and a span of time in other units ("three months" for "90 days") is a mismatch.
"""

import logging
import re
from typing import Any

from pipeline.state import PipelineState
from utils.citations import is_placeholder_line
from utils.frames import chunk_field
from utils.sentences import event_quote_failure
from utils.specifics import unsupported_specifics
from utils.text_spans import protected_spans

logger = logging.getLogger(__name__)

ISSUE_TYPES = (
    "citation_malformed", "citation_unknown_id", "uncited_span", "specific_not_in_cited_source",
    "view_contains_specific", "event_unverified", "mixed_authorship_span", "over_length", "banned_text",
)

# How the request is named where a source id would be: a specific found in the
# topic or the context, not in a source.
REQUEST = "request"
EM_DASH = "—"
# Why an EVENT line that is not a usable citation leaves the event unverified.
_EVENT_LINE_REASONS = {"missing": "event_line_missing", "malformed": "event_line_malformed",
                       "unexpected": "event_line_unexpected"}


def _issue(issue_type: str, span: int | None, text: str, sources=(), /, **detail: Any) -> dict[str, Any]:
    return {"type": issue_type, "span": span, "text": text, "sources": list(sources), "detail": detail}


def _chunk_text(chunk: dict) -> str:
    return chunk_field(chunk, "text") or chunk_field(chunk, "content")


def _source_texts(source_index: dict, chunks: list[dict]) -> dict[str, str]:
    """S-id -> that source's text, by the position the index recorded for it."""
    return {sid: _chunk_text(chunks[entry["position"]]) for sid, entry in source_index.items()
            if entry["position"] < len(chunks)}


def _found_in(specific_text: str, texts: dict[str, str], request: list[str], exclude=()) -> list[str]:
    """Where else a specific is stated: source ids, and REQUEST for the topic or context."""
    found = [sid for sid, text in texts.items()
             if sid not in exclude and not unsupported_specifics(specific_text, [text], convert_units=False)]
    if not unsupported_specifics(specific_text, request, convert_units=False):
        found.append(REQUEST)
    return found


# ── The checks ────────────────────────────────────────────────────────────────

def citation_malformed(marker_failures: list[dict]) -> list[dict]:
    """Marker-like text that is not a usable citation: what stripping the draft
    reported (malformed, single_brackets, unbalanced, empty_span), or markers
    left in a finished post."""
    return [_issue("citation_malformed", None, f["text"], kind=f["kind"], start=f["start"], end=f["end"])
            for f in marker_failures]


def citation_unknown_id(spans: list[dict], source_index: dict) -> list[dict]:
    issues = []
    for i, span in enumerate(spans):
        unknown = [sid for sid in span["sources"] if sid not in source_index]
        if unknown:
            issues.append(_issue("citation_unknown_id", i, span["text"], span["sources"], unknown=unknown))
    return issues


def uncited_span(spans: list[dict]) -> list[dict]:
    """Prose with no marker. Headings, placeholder lines and code never become
    spans (utils.citations), so they are not here."""
    return [_issue("uncited_span", i, span["text"]) for i, span in enumerate(spans) if span["basis"] == "uncited"]


def specific_not_in_cited_source(spans: list[dict], texts: dict[str, str], request: list[str]) -> list[dict]:
    """A number, percentage, amount, duration, month, weekday or time phrase in
    a span that the span's own sources do not state. For a span citing the
    request, the sources are the topic and the context. detail.found_in names
    any other place that does state it."""
    issues = []
    for i, span in enumerate(spans):
        if span["basis"] == "sources":
            cited = [sid for sid in span["sources"] if sid in texts]
            if not cited:
                continue                     # only unknown ids: citation_unknown_id reports that
            against, exclude = [texts[sid] for sid in cited], cited
        elif span["basis"] == "request":
            against, exclude = request, ()
        else:
            continue
        for specific in unsupported_specifics(span["text"], against, convert_units=False):
            found = [f for f in _found_in(specific.text, texts, request, exclude)
                     if not (span["basis"] == "request" and f == REQUEST)]
            issues.append(_issue("specific_not_in_cited_source", i, span["text"], span["sources"],
                                 specific=specific.text, kind=specific.kind, found_in=found))
    return issues


def view_contains_specific(spans: list[dict], texts: dict[str, str], request: list[str]) -> list[dict]:
    """Any specific in a span marked as the author's view. A view states no
    fact, so there is nothing for it to be checked against: the specific has to
    be cited or go. detail.found_in names where it is stated, if anywhere."""
    issues = []
    for i, span in enumerate(spans):
        if span["basis"] != "view":
            continue
        for specific in unsupported_specifics(span["text"], [], convert_units=False):
            issues.append(_issue("view_contains_specific", i, span["text"], (),
                                 specific=specific.text, kind=specific.kind,
                                 found_in=_found_in(specific.text, texts, request)))
    return issues


def event_unverified(event: dict | None, source_index: dict, chunks: list[dict]) -> list[dict]:
    """A story post whose event is not verified: no usable EVENT line, or one
    that cites an id that is not a source, a source that is not the author's
    own experience, or a sentence that is not in that source word for word."""
    if not event:
        return []
    status = event.get("status")
    if status in _EVENT_LINE_REASONS:
        return [_issue("event_unverified", None, event.get("line") or "", reason=_EVENT_LINE_REASONS[status])]
    if status != "cited":
        return []                            # "none" (written as a General Post) or "absent" (not a story)
    sid, line = event["source"], event.get("line") or ""
    entry = source_index.get(sid)
    if entry is None or entry["position"] >= len(chunks):
        return [_issue("event_unverified", None, line, [sid], reason="unknown_source")]
    if entry["authorship"] != "self":
        return [_issue("event_unverified", None, line, [sid], reason="source_not_own_experience",
                       frame=entry["frame"])]
    failure = event_quote_failure(event.get("quote"), chunks[entry["position"]])
    if failure:
        return [_issue("event_unverified", None, line, [sid], reason=failure)]
    return []


def mixed_authorship_span(spans: list[dict], source_index: dict) -> list[dict]:
    """One span citing both the author's own experience and an external source."""
    issues = []
    for i, span in enumerate(spans):
        by_authorship: dict[str, list[str]] = {}
        for sid in span["sources"]:
            if sid in source_index:
                by_authorship.setdefault(source_index[sid]["authorship"], []).append(sid)
        if len(by_authorship) > 1:
            issues.append(_issue("mixed_authorship_span", i, span["text"], span["sources"],
                                 self=by_authorship.get("self", []), external=by_authorship.get("external", [])))
    return issues


def over_length(validation: dict | None) -> list[dict]:
    """The post is over its maximum (from the finalise record). A post under its
    minimum is recorded there and is not an issue."""
    if not validation or validation.get("length") != "over_length":
        return []
    return [_issue("over_length", None, "", words=validation["words"],
                   max_words=validation["target"]["max_words"], over_by=validation["over_by"])]


def _whole_words(words: str) -> re.Pattern:
    """words as whole words, any case, straight or curly apostrophes."""
    pattern = re.escape(words).replace("'", "['’]")
    return re.compile(rf"(?<!\w){pattern}(?!\w)", re.IGNORECASE)


def banned_text(text: str, spans: list[dict], profile: dict, first_post: bool) -> list[dict]:
    """Text a post must not contain, by a rule that can be matched exactly: an
    em dash outside code, URLs and quoted literals (a product rule about one
    character); one of the words this author listed to avoid (the profile's
    words_to_avoid: the user's own rule, matched as whole words in any case);
    and, in a first post, a [DIAGRAM: ...] or [IMAGE: ...] placeholder.

    There is no list of banned phrases here and there must not be one: whether
    wording sounds machine-written is a judgement, made by the structured
    review, not a lookup."""
    def span_at(offset: int) -> int | None:
        return next((i for i, s in enumerate(spans) if s["start"] <= offset < s["end"]), None)

    def where(offset: int, matched: str) -> tuple[int | None, str]:
        i = span_at(offset)
        return i, spans[i]["text"] if i is not None else matched

    issues = []
    protected = protected_spans(text)
    for offset, char in enumerate(text):
        if char == EM_DASH and not any(start <= offset < end for start, end in protected):
            i, shown = where(offset, EM_DASH)
            issues.append(_issue("banned_text", i, shown, kind="em_dash", offset=offset))
    for word in profile.get("words_to_avoid") or []:
        if not word or not word.strip():
            continue
        for match in _whole_words(word.strip()).finditer(text):
            i, shown = where(match.start(), match.group(0))
            issues.append(_issue("banned_text", i, shown, kind="word_to_avoid", word=word, offset=match.start()))
    if first_post:
        offset = 0
        for line in text.split("\n"):
            if is_placeholder_line(line):
                issues.append(_issue("banned_text", None, line.strip(), kind="placeholder_in_first_post", offset=offset))
            offset += len(line) + 1
    return sorted(issues, key=lambda issue: issue["detail"]["offset"])


# ── Running them ──────────────────────────────────────────────────────────────

def run_checks(state: PipelineState, marker_failures: list[dict]) -> dict[str, Any]:
    """Every check on the post as it stands in state: {issues, counts}.

    marker_failures: what to report as citation_malformed. For the draft it is
    what stripping its markers found; for a post changed since (a trim), the
    marker-like text still in it.
    """
    spans = state.get("citations") or []
    source_index = state.get("source_index") or {}
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    texts = _source_texts(source_index, chunks)
    request = [state.get("topic") or "", state.get("context") or ""]
    issues = [
        *citation_malformed(marker_failures),
        *citation_unknown_id(spans, source_index),
        *uncited_span(spans),
        *specific_not_in_cited_source(spans, texts, request),
        *view_contains_specific(spans, texts, request),
        *event_unverified(state.get("event"), source_index, chunks),
        *mixed_authorship_span(spans, source_index),
        *over_length(state.get("final_validation")),
        *banned_text(state.get("final_post") or "", spans, state.get("profile") or {}, bool(state.get("first_post"))),
    ]
    counts = {kind: sum(1 for issue in issues if issue["type"] == kind) for kind in ISSUE_TYPES}
    return {"issues": issues, "counts": {kind: n for kind, n in counts.items() if n}}


def checks_node(state: PipelineState) -> PipelineState:
    """Check the finalised draft. Recorded only: nothing here changes the post.

    Sets checks_before_trim, and checks_final to the same result: it stays the
    final one unless a trim changes the post and recheck_node replaces it.
    """
    result = run_checks(state, state.get("citation_failures") or [])
    state["checks_before_trim"] = state["checks_final"] = result
    if result["issues"]:
        logger.info("checks: %s", result["counts"])
    return state


def recheck_node(state: PipelineState) -> PipelineState:
    """Check the post again after a trim changed it: the checks on the text
    that is returned (checks_final)."""
    leftover = (state.get("final_validation") or {}).get("leftover_markers") or []
    state["checks_final"] = run_checks(state, leftover)
    return state
