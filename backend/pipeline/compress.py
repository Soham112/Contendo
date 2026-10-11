"""Compress, the code half: which of the model's shorter replacements may be
used, and how they are spliced into the post. No model calls
(agents/compress_agent.py makes the one call).

A replacement is used only when all of these hold; otherwise its sentence stays
as it was and the reason is recorded:

    unknown_sentence    the number is not one of the post's sentences
    repeated            the number is given more than once (none of them is used)
    deletion            the entry asks for the sentence to be left out
    empty               the replacement has no prose
    marker_failure      it holds marker-like text that is not a valid marker
    not_one_sentence    it is more than one sentence, or more than one cited
                        piece: sentences are never merged or added
    changes_sentence_boundaries  the spliced post changes sentence count or positions
    marker_missing      it has no marker and its sentence has one
    marker_wrong        its marker is not exactly its sentence's
    list_marker_lost    its sentence begins with a list marker ("- ", "* ", "1. ")
                        and it does not begin with the same one
    not_shorter         it does not have fewer words than its sentence
    new_specific        it holds a number, date or time reference its sentence
                        does not (utils.specifics.extract_specifics)

Nothing here judges meaning: these are checks on ids, counts and a closed
vocabulary. Whether a shorter sentence still says the same thing is the model's
job, bounded by what the checks rule out: a sentence cannot disappear, grow,
change what it cites or gain a figure.

Sentences are the post's spans cut by utils.sentences.split_spans, the same
numbering the review and the targeted fix use. The splice replaces the accepted
sentences' own characters and nothing else, so every other character of the
post is the one that was there before.
"""

from dataclasses import dataclass
from typing import Sequence

from pipeline.finalise import finalise_marked
from utils.citations import Span, marked, marker
from utils.draft_output import Fix
from utils.formatters import count_words
from utils.sentences import list_marker, sentence_offsets, split_spans
from utils.specifics import extract_specifics


@dataclass(frozen=True)
class Compressed:
    text: str                      # the post with the accepted replacements in place
    spans: tuple[Span, ...]        # its spans: the same spans, over the new text
    accepted: tuple[dict, ...]     # {sentence, before, after, words_before, words_after}; before/after with markers
    rejected: tuple[dict, ...]     # {sentence, reason, text}; text is what the model gave


# STOPGAP: structural checks (length, marker, specifics, list marker, sentence
# boundaries) do not verify meaning: stance can change or a name/event can be added.
# Proper fix: semantic verification of each replacement against its original,
# as part of eval/faithfulness-judge.
def _usable(original: Span, given: str | None) -> Span | str:
    """The replacement as a span of its own text (offsets from 0), or why it
    cannot be used. Its punctuation is normalised as finalise() would, so what
    is measured here is what is spliced."""
    if given is None:
        return "deletion"
    finalised, stripped = finalise_marked(given.strip(), None)
    if not stripped.spans:
        return "empty"
    if stripped.failures:
        return f"marker_failure: {[failure.kind for failure in stripped.failures]}"
    replacement = stripped.spans[0]
    if (len(stripped.spans) > 1 or finalised.text.strip() != replacement.text
            or len(split_spans(stripped.spans)) != 1):
        return "not_one_sentence"
    if marker(replacement) != marker(original):
        return "marker_wrong" if marker(replacement) else "marker_missing"
    if list_marker(original.text) and list_marker(replacement.text) != list_marker(original.text):
        return "list_marker_lost"
    if count_words(replacement.text) >= count_words(original.text):
        return "not_shorter"
    # STOPGAP: money keys omit currency identity, so equal amounts in different
    # currencies compare equal (the extractor also labels its currency stopgap).
    # Proper fix: structured money extraction (amount + currency) in planned specifics work.
    known = {specific.key for specific in extract_specifics(original.text)}
    new = [specific.text for specific in extract_specifics(replacement.text) if specific.key not in known]
    if new:
        return f"new_specific: {new}"
    return Span(0, len(replacement.text), replacement.text, original.basis, original.sources)


def _splice(text: str, spans: Sequence[Span], units: Sequence[tuple[int, Span]],
            edits: dict[int, Span]) -> tuple[str, tuple[Span, ...]]:
    """text with the sentences at the positions in `edits` replaced, and the
    post's spans over the result. Everything outside those sentences is copied
    as it stands."""
    pieces: list[str] = []
    bounds: dict[int, tuple[int, int]] = {}      # span position -> (start, end) in the new text
    cursor = length = 0
    for index, (position, sentence) in enumerate(units):
        between = text[cursor:sentence.start]
        body = edits[index].text if index in edits else sentence.text
        start = length + len(between)
        length = start + len(body)
        pieces += [between, body]
        bounds[position] = (bounds[position][0] if position in bounds else start, length)
        cursor = sentence.end
    pieces.append(text[cursor:])
    new_text = "".join(pieces)
    return new_text, tuple(Span(start, end, new_text[start:end], spans[position].basis, spans[position].sources)
                           for position, (start, end) in sorted(bounds.items()))


def _same_boundaries(text: str, units: Sequence[tuple[int, Span]],
                     edits: dict[int, Span], candidate: str) -> bool:
    """Re-segment the whole post, including across citation-span boundaries.

    The candidate must have exactly the original sentence sequence, substituting
    each edited unit at its original position. List prefixes are excluded by the
    shared splitter; punctuationless items therefore remain valid sentences.
    """
    expected = []
    matched: set[int] = set()
    for start, end in sentence_offsets(text):
        overlaps = [index for index in edits
                    if units[index][1].start < end and start < units[index][1].end]
        if not overlaps:
            expected.append(text[start:end])
            continue
        if len(overlaps) != 1:
            return False
        index = overlaps[0]
        original, replacement = units[index][1], edits[index]
        if index in matched or not original.start <= start < end <= original.end:
            return False
        offsets = sentence_offsets(replacement.text)
        if len(offsets) != 1:
            return False
        begin, finish = offsets[0]
        expected.append(replacement.text[begin:finish])
        matched.add(index)
    actual = [candidate[start:end] for start, end in sentence_offsets(candidate)]
    return matched == set(edits) and actual == expected


def apply_replacements(text: str, spans: Sequence[Span], fixes: Sequence[Fix]) -> Compressed:
    """Validate each replacement against its sentence and splice in the ones
    that pass (see the module docstring for the rules)."""
    units = split_spans(spans)
    by_number: dict[int, list[Fix]] = {}
    for fix in fixes:
        by_number.setdefault(fix.sentence, []).append(fix)

    edits: dict[int, Span] = {}
    accepted, rejected = [], []
    for number, given in by_number.items():
        shown = given[0].text or ""
        if not 1 <= number <= len(units):
            rejected.append({"sentence": number, "reason": "unknown_sentence", "text": shown})
            continue
        if len(given) > 1:
            rejected.append({"sentence": number, "reason": "repeated", "text": shown})
            continue
        original = units[number - 1][1]
        replacement = _usable(original, given[0].text)
        if isinstance(replacement, str):
            rejected.append({"sentence": number, "reason": replacement, "text": shown})
            continue
        proposed = {**edits, number - 1: replacement}
        candidate, _ = _splice(text, spans, units, proposed)
        if not _same_boundaries(text, units, proposed, candidate):
            rejected.append({"sentence": number, "reason": "changes_sentence_boundaries", "text": shown})
            continue
        edits = proposed
        accepted.append({"sentence": number, "before": marked(original), "after": marked(replacement),
                         "words_before": count_words(original.text), "words_after": count_words(replacement.text)})
    new_text, new_spans = _splice(text, spans, units, edits) if edits else (text, tuple(spans))
    return Compressed(new_text, new_spans, tuple(sorted(accepted, key=lambda entry: entry["sentence"])),
                      tuple(rejected))
