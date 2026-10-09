"""Sentence spans in author notes; pysbd is isolated behind note_sentences.

Line breaks and Markdown bullet/numbered-list items delimit thoughts even when
terminal punctuation is absent. Code/URL punctuation is masked at equal-length
source offsets before segmentation, so the returned text is always from the note.
"""
import re

import pysbd

from utils.text_spans import protected_spans

_LIST_PREFIX = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")


def note_sentences(text: str) -> list[str]:
    """Original sentence/line/item text, excluding syntactic list markers.

    Pysbd handles initials, abbreviations, decimals and quoted sentences. Line
    breaks within protected code/URLs do not introduce thought boundaries.
    """
    # Segmenter stores original_text internally; never share it across requests.
    segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)
    masked = list(text)
    for start, end in protected_spans(text, quoted_literals=False):
        masked[start:end] = "x" * (end - start)
    masked_text = "".join(masked)
    sentences, offset = [], 0
    for line in masked_text.splitlines(keepends=True):
        prefix = _LIST_PREFIX.match(line)
        start = prefix.end() if prefix else 0
        for span in segmenter.segment(line[start:]):
            original = text[offset + start + span.start:offset + start + span.end].strip()
            if original:
                sentences.append(original)
        offset += len(line)
    return sentences


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
