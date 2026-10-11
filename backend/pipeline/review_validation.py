"""Checks on the review model's merged answer before any issue is derived from
it (agents/review_agent.py). No model calls.

- coverage_error: every sentence sent must have exactly one record.
- validate_records: a record that names an id that is not a source of this run,
  or whose evidence is not in one of its sources word for word, is invalid as a
  whole. A record's detail_change and unsupported_part are checked on their
  own: one that fails is dropped from the record and reported, and the rest of
  the record still counts.

Records are the review's SentenceRecord objects; only their fields are read here.
"""

from typing import Any

from pipeline.review_rules import REQUEST
from utils.citations import Span
from utils.sentences import is_verbatim_span
from utils.wording import same_wording


def coverage_error(numbers: list[int], expected: list[int]) -> str | None:
    """Why the merged records do not cover the sentences sent exactly once, or None."""
    missing = [n for n in expected if n not in numbers]
    repeated = sorted({n for n in numbers if numbers.count(n) > 1})
    unknown = sorted({n for n in numbers if n not in expected})
    if not (missing or repeated or unknown):
        return None
    return f"sentence_coverage: missing {missing}, repeated {repeated}, unknown {unknown}"


def _invalid_reason(record: Any, source_texts: dict[str, str], request_text: str) -> str | None:
    """Why a whole record cannot be used, or None."""
    link_ids = [*record.link.sources, *record.link.stated_by] if record.link else []
    unknown = sorted({sid for sid in [*record.supported_by, *link_ids] if sid != REQUEST and sid not in source_texts})
    if unknown:
        return f"unknown_source: {unknown}"
    if REQUEST in link_ids:
        return "request_is_not_a_link_source"
    evidence = (record.evidence or "").strip()
    if not evidence:
        return None
    if not record.supported_by:
        return "evidence_without_source"
    places = [request_text if sid == REQUEST else source_texts[sid] for sid in record.supported_by]
    if not any(is_verbatim_span(evidence, text) for text in places):
        return "evidence_not_in_source"
    return None


def _detail_problem(record: Any, sentence: str, source_texts: dict[str, str], request_text: str) -> str | None:
    """Why a record's detail_change cannot be used, or None (also when it has none)."""
    change = record.detail_change
    if change is None:
        return None
    places = [request_text if sid == REQUEST else source_texts[sid] for sid in record.supported_by]
    if not any(is_verbatim_span(change.source_words, text) for text in places):
        return "source_words_not_in_a_supporting_source"
    if not is_verbatim_span(change.post_words, sentence):
        return "post_words_not_in_the_sentence"
    if same_wording(change.source_words, change.post_words):
        return "same_wording"
    return None


def validate_records(records: list[Any], sentences: list[tuple[int, Span]], source_texts: dict[str, str],
                     request_text: str) -> tuple[list[dict], list[int], list[dict]]:
    """(usable, positions, invalid) for the merged records, in sentence order.

    usable: the records that can be used, as dicts, with a detail_change or
    unsupported_part that failed its check set to None. positions: the 0-based
    sentence each usable record describes. invalid: what failed, each
    {sentence, text, reason, record}; sentence is 0-based.
    """
    usable_records, positions, invalid = [], [], []

    def report(record: Any, reason: str, what: Any) -> None:
        invalid.append({"sentence": record.sentence - 1, "text": sentences[record.sentence - 1][1].text,
                        "reason": reason, "record": what})

    for record in sorted(records, key=lambda r: r.sentence):
        text = sentences[record.sentence - 1][1].text
        reason = _invalid_reason(record, source_texts, request_text)
        if reason:
            report(record, reason, record.model_dump(exclude_defaults=True))
            continue
        usable = record.model_dump()
        problem = _detail_problem(record, text, source_texts, request_text)
        if problem:
            report(record, f"invalid_detail: {problem}", usable.pop("detail_change"))
            usable["detail_change"] = None
        if record.unsupported_part and not is_verbatim_span(record.unsupported_part, text):
            report(record, "invalid_unsupported_part: not_in_the_sentence", record.unsupported_part)
            usable["unsupported_part"] = None
        usable_records.append(usable)
        positions.append(record.sentence - 1)
    return usable_records, positions, invalid
