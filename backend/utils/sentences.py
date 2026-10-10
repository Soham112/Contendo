"""Sentence spans in author notes and in a post's spans; pysbd is isolated here.

Line breaks and Markdown bullet/numbered-list items delimit thoughts even when
terminal punctuation is absent. Code/URL punctuation is masked at equal-length
source offsets before segmentation, so the returned text is always from the note.
"""
import re
from typing import Sequence

import pysbd

from utils.citations import Span
from utils.frames import chunk_field
from utils.text_spans import protected_spans

_LIST_PREFIX = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")


def sentence_offsets(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence/line/item in text, excluding list markers.

    Pysbd handles initials, abbreviations, decimals and quoted sentences. Line
    breaks within protected code/URLs do not introduce thought boundaries.
    """
    # Segmenter stores original_text internally; never share it across requests.
    segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)
    masked = list(text)
    for start, end in protected_spans(text, quoted_literals=False):
        masked[start:end] = "x" * (end - start)
    masked_text = "".join(masked)
    offsets, offset = [], 0
    for line in masked_text.splitlines(keepends=True):
        prefix = _LIST_PREFIX.match(line)
        start = prefix.end() if prefix else 0
        for span in segmenter.segment(line[start:]):
            begin = offset + start + span.start
            raw = text[begin:offset + start + span.end]
            original = raw.strip()
            if original:
                begin += len(raw) - len(raw.lstrip())
                offsets.append((begin, begin + len(original)))
        offset += len(line)
    return offsets


def note_sentences(text: str) -> list[str]:
    """Original sentence/line/item text, excluding syntactic list markers."""
    return [text[start:end] for start, end in sentence_offsets(text)]


def split_spans(spans: Sequence[Span]) -> list[tuple[int, Span]]:
    """A post's spans cut into sentences: (position of the span it came from, sentence).

    Each sentence is a Span over the same text as its span, with that span's
    basis and sources: a sentence inherits its span's citation. The first
    sentence starts where the span starts and the last ends where it ends, so
    a list marker or closing punctuation stays with a sentence. Code and URLs
    are never split (sentence_offsets). A span the segmenter finds no sentence
    in is one unit.
    """
    units: list[tuple[int, Span]] = []
    for position, span in enumerate(spans):
        offsets = sentence_offsets(span.text) or [(0, len(span.text))]
        last = len(offsets) - 1
        for i, (start, end) in enumerate(offsets):
            start = 0 if i == 0 else start
            end = len(span.text) if i == last else end
            units.append((position, Span(span.start + start, span.start + end, span.text[start:end],
                                         span.basis, span.sources)))
    return units


def multi_sentence_span_count(spans: Sequence[Span]) -> int:
    """How many spans hold more than one sentence. The drafter is asked for a
    marker on every sentence, so this measures how far a draft kept to that."""
    per_span: dict[int, int] = {}
    for position, _ in split_spans(spans):
        per_span[position] = per_span.get(position, 0) + 1
    return sum(1 for count in per_span.values() if count > 1)


def note_quote_spans(text: str) -> list[str]:
    """Sentence/line/item ends with starts at the beginning or a prose colon.

    Literal colons (including URLs/code) and digit-to-digit time separators do
    not introduce starts. Colon suffixes retain the segmenter's original end.
    """
    candidates = []
    for sentence in note_sentences(text):
        candidates.append(sentence)
        literals = protected_spans(sentence, quoted_literals=False)
        for index, char in enumerate(sentence):
            if char != ":" or any(start <= index < end for start, end in literals):
                continue
            before, after = sentence[:index].rstrip(), sentence[index + 1:].lstrip()
            if before[-1:].isdigit() and after[:1].isdigit():
                continue
            if after:
                candidates.append(after)
    return candidates


# ── Verbatim event quotes ─────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace: deliberate quote tolerances."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def event_quote_failure(quote: str | None, note: dict) -> str | None:
    """Verify a sentence/line/item end, starting at its beginning or a prose colon.

    Literal/time colons are not starts; this checks syntax, never topic fit.
    """
    wanted = _normalise(quote or "")
    text = chunk_field(note, "text") or chunk_field(note, "content")
    if not wanted:
        return "event_quote_missing"
    if wanted in {_normalise(sentence) for sentence in note_quote_spans(text)}:
        return None
    normalised = _normalise(text)
    if wanted not in normalised:
        return "event_quote_not_in_note"
    # This regex matches a literal copied span, not meaning or model intent.
    if not re.search(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)", normalised):
        return "event_quote_partial_word"
    return "event_quote_not_sentence"


def quote_is_in_note(quote: str | None, note: dict) -> bool:
    return event_quote_failure(quote, note) is None
