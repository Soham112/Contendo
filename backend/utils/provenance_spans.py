"""Paragraphs with character offsets, for provenance (step 3.3).

The provenance classifier labels numbered paragraphs; their labels are stored
as offsets into the source's extracted_text, so they survive re-chunking.
Splitting is structural only: blank lines, then sentence-ending punctuation for
paragraphs too long to label as one (transcripts often have no breaks).
"""
import re
from dataclasses import dataclass

# A paragraph longer than this is split at sentence ends.
MAX_PARAGRAPH_CHARS = 2_000
# One classifier call sees at most this much text; longer sources go in parts.
MAX_PART_CHARS = 60_000

_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s+")


@dataclass(frozen=True)
class Paragraph:
    id: int       # 1-based, in text order
    start: int    # offsets into the text: text[start:end]
    end: int


def _trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Cut [start, end) into pieces of at most MAX_PARAGRAPH_CHARS, at the last
    sentence end before the limit, or at the limit when there is none."""
    pieces = []
    while end - start > MAX_PARAGRAPH_CHARS:
        limit = start + MAX_PARAGRAPH_CHARS
        cut = None
        for match in _SENTENCE_END.finditer(text, start, limit):
            cut = match.end()
        cut = cut if cut and cut > start else limit
        pieces.append(_trimmed(text, start, cut))
        start = cut
    pieces.append(_trimmed(text, start, end))
    return [(s, e) for s, e in pieces if e > s]


def paragraphs(text: str) -> list[Paragraph]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in [*_BLANK_LINE.finditer(text), None]:
        end = match.start() if match else len(text)
        s, e = _trimmed(text, start, end)
        if e > s:
            spans.extend(_split_long(text, s, e))
        if match:
            start = match.end()
    return [Paragraph(i, s, e) for i, (s, e) in enumerate(spans, start=1)]


def parts(paras: list[Paragraph]) -> list[list[Paragraph]]:
    """Consecutive groups of paragraphs, each spanning at most MAX_PART_CHARS
    (a single paragraph never exceeds it)."""
    groups: list[list[Paragraph]] = []
    for para in paras:
        if groups and para.end - groups[-1][0].start <= MAX_PART_CHARS:
            groups[-1].append(para)
        else:
            groups.append([para])
    return groups


def merge_runs(paras: list[Paragraph], labels: dict[int, str]) -> list[dict]:
    """Contiguous paragraphs with the same label as one span each:
    [{"start", "end", "authorship"}], for the paragraphs that have a label."""
    spans: list[dict] = []
    previous: Paragraph | None = None
    for para in paras:
        label = labels.get(para.id)
        if label is None:
            previous = None
            continue
        if spans and previous is not None and spans[-1]["authorship"] == label:
            spans[-1]["end"] = para.end
        else:
            spans.append({"start": para.start, "end": para.end, "authorship": label})
        previous = para
    return spans
