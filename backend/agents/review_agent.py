"""The structured review of a single-writer post: it describes every sentence,
and never judges or writes.

The deterministic checks (pipeline/checks.py) decide what code can decide from
the text alone. What is left needs reading: does a source state this, is it told
as fact or as the author's view, is it presented as the author's own. The model
answers those as observations, one compact record per sentence. It is not asked
whether a sentence is a problem, and it is not shown the post's citations: what
a sentence was cited to is the writer's claim, and code compares it with what
the model finds. pipeline/review_rules.py turns the observations into issues by
fixed rules.

A long post is reviewed in parallel. The sentences are split into groups; each
group gets its own call, which sees the whole post and all the sources for
context but records only its own sentences. The answers are merged in code.

Code checks the merged answer before using it:
- every sentence must have exactly one record: a missing or repeated sentence
  number, a group that fails or is cut off, means the post was not reviewed;
- a record that names an id that is not a source of this run, or whose evidence
  is not in one of its sources word for word, is invalid: it is reported, and
  no issue is derived from it;
- the two fields that quote the post are each checked on their own. A
  detail_change must quote the source and the sentence word for word, and the
  two must differ by more than their form (utils.wording.same_wording). An
  unsupported_part must be words of the sentence. One that fails is dropped
  from the record and reported (invalid_detail, invalid_unsupported_part); the
  rest of the record still counts.

The prompt is built in agents/review_prompt.py; this file holds the call, the
merge and the validation. review_post() is not wired into the pipeline yet
(feat/single-writer step 6b).
"""

import contextvars
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from llm.client import (
    MAX_NON_STREAMING_OUTPUT_TOKENS, SONNET, StructuredOutputError, TruncatedStructuredOutputError,
    complete_structured, trace_calls,
)
from agents.review_prompt import build_review_prompt
from pipeline.review_rules import REQUEST, derive_issues
from pipeline.state import PipelineState
from utils.citations import Span
from utils.frames import chunk_field
from utils.sentences import is_verbatim_span, split_spans
from utils.wording import same_wording

logger = logging.getLogger(__name__)

# The review model. Per-role model configuration comes in step 7 of the plan.
REVIEW_MODEL = SONNET

# Parallel review. A call's time is mostly its output, so a group is sized to
# finish inside the 10 s target for a full-post review. Measured in the 6a-4
# live check (2026-10-09): 55 to 63 output tokens a second, and a group of six
# sentences that wrote 701 tokens took 11.2 s. Four sentences at up to 150
# tokens each is about 600 tokens: about 10 s at the slower rate.
SENTENCES_PER_GROUP = 4
# Every group resends the whole prompt (the sources and the post: about 4,100
# input tokens for a standard post, a little over a cent), so each extra group
# costs that much. Past this many groups the groups get larger instead, and a
# long article takes longer than the target rather than costing more per sentence.
MAX_REVIEW_GROUPS = 6
# Output budget for one group: its records, plus the rhythm list. Measured in
# the 6a-4 live check: 105 output tokens per sentence on average across two
# full posts, and 143 in the heaviest group (rhythm notes included).
_TOKENS_PER_RECORD = 150
_REVIEW_BASE_TOKENS = 300

Content = Literal["fact_or_event", "feeling_or_reaction", "motive", "generalisation", "opinion",
                  "advice_or_question", "analogy_or_comparison", "disclaimer", "other"]
StatedAs = Literal["fact", "authors_view"]
PresentedAs = Literal["author_did_or_experienced", "a_source_says", "authors_view", "neutral"]


class DetailChange(BaseModel):
    source_words: str = Field(description="The source's words that carry the detail, copied word for word.")
    post_words: str = Field(description="The sentence's words that carry the changed detail, copied from the sentence.")


class Link(BaseModel):
    sources: list[str] = Field(description="Ids of the sources the linked facts come from.")
    stated_by: list[str] = Field(default_factory=list, description="Ids of the sources that state that link themselves.")


class SentenceRecord(BaseModel):
    """What one sentence does. Four fields are always given; the rest only when they apply."""
    sentence: int = Field(description="The sentence's number, as numbered in the post.")
    content: Content = Field(description="What kind of thing the sentence mainly says.")
    stated_as: StatedAs = Field(description="Whether it is stated as simply true, or as the author's view.")
    presented_as: PresentedAs = Field(description="Whose the sentence presents its content as being.")
    supported_by: list[str] = Field(
        default_factory=list,
        description='Ids of the sources that state what the sentence says, and/or "request". Omit when nothing states it.')
    evidence: str | None = Field(
        default=None, description="Words copied from one of the supported_by sources that state it. Omit without supported_by.")
    unsupported_part: str | None = Field(
        default=None, description="The exact words of the sentence that nothing states. Omit when there are none.")
    detail_change: DetailChange | None = Field(
        default=None, description="A detail the sentence gives differently from the source. Omit when there is none.")
    link: Link | None = Field(
        default=None, description="Present only when the sentence links facts as cause, sequence or result.")
    off_topic: bool = Field(default=False, description="True when the sentence leaves the topic. Omit otherwise.")


class RhythmNote(BaseModel):
    sentence: int = Field(description="The number of the sentence where it shows most.")
    why: str = Field(description="One short sentence describing the pattern. Never replacement wording.")


class Review(BaseModel):
    sentences: list[SentenceRecord]
    ai_rhythm: list[RhythmNote] = Field(default_factory=list)


def post_sentences(citations: list[dict]) -> list[tuple[int, Span]]:
    """The post's sentences as the review numbers them: (position of the span
    it came from, sentence). Each sentence has its span's citation, which the
    review model is not shown."""
    return split_spans([Span.from_dict(c) for c in citations])


def review_groups(sentence_count: int) -> list[range]:
    """The sentence numbers (1-based) each parallel call records: contiguous
    groups of about SENTENCES_PER_GROUP, never more than MAX_REVIEW_GROUPS."""
    if sentence_count <= 0:
        return []
    groups = min(MAX_REVIEW_GROUPS, math.ceil(sentence_count / SENTENCES_PER_GROUP))
    size, extra = divmod(sentence_count, groups)
    bounds, start = [], 1
    for g in range(groups):
        end = start + size + (1 if g < extra else 0)
        bounds.append(range(start, end))
        start = end
    return bounds


def group_max_tokens(sentence_count: int) -> int:
    """The output budget of the call that records this many sentences."""
    return min(MAX_NON_STREAMING_OUTPUT_TOKENS,
               _REVIEW_BASE_TOKENS + math.ceil(sentence_count * _TOKENS_PER_RECORD))


def _coverage_error(numbers: list[int], sentence_count: int) -> str | None:
    """Why the merged records do not cover the post's sentences exactly once, or None."""
    missing = [n for n in range(1, sentence_count + 1) if n not in numbers]
    repeated = sorted({n for n in numbers if numbers.count(n) > 1})
    unknown = sorted({n for n in numbers if not 1 <= n <= sentence_count})
    if not (missing or repeated or unknown):
        return None
    return f"sentence_coverage: missing {missing}, repeated {repeated}, unknown {unknown}"


def _invalid_reason(record: SentenceRecord, source_texts: dict[str, str], request_text: str) -> str | None:
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


def _detail_problem(record: SentenceRecord, sentence: str, source_texts: dict[str, str], request_text: str) -> str | None:
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


def _review_group(state: PipelineState, sentences: list[tuple[int, Span]], group: range) -> Review:
    return complete_structured(
        schema=Review,
        tool_name="record_review",
        tool_description="Record one entry for each assigned sentence of the post, then the ai_rhythm list.",
        model=REVIEW_MODEL,
        max_tokens=group_max_tokens(len(group)),
        messages=[{"role": "user", "content": build_review_prompt(state, sentences, group)}],
        user_id=state["user_id"],
        event_type="review",
    )


def _failure(exc: BaseException) -> str:
    if isinstance(exc, TruncatedStructuredOutputError):
        return "truncated"
    if isinstance(exc, StructuredOutputError):
        return f"invalid_output: {exc}"
    return f"api_error: {type(exc).__name__}"


def review_post(state: PipelineState) -> dict[str, Any]:
    """Review the post in state. Changes nothing.

    Returns {outcome, issues, invalid, records, groups, model, input_tokens,
    output_tokens} and, when the review did not happen, error:
      outcome "clean"         the review ran and the rules derived no issue
      outcome "issues"        at least one issue
      outcome "not_reviewed"  a group's call failed or its answer could not be
                              used (truncated, not a valid tool call), or the
                              merged records do not cover every sentence exactly
                              once. Never treated as clean.
    records   the model's observations, one per sentence, merged from the groups
    groups    how many parallel calls made the review
    issues    derived in code (pipeline.review_rules.derive_issues) from the
              valid records, plus the ai_rhythm notes: {type, sentence, span,
              text, sources, evidence, detail}; sentence is 0-based
    invalid   what failed validation, each with a reason: whole records (nothing
              is derived from them), a record's detail_change or unsupported_part
              on its own (invalid_detail, invalid_unsupported_part: only that
              field is dropped), and rhythm notes.
    """
    sentences = post_sentences(state.get("citations") or [])
    source_index = state.get("source_index") or {}
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    source_texts = {sid: chunk_field(chunks[entry["position"]], "text") or chunk_field(chunks[entry["position"]], "content")
                    for sid, entry in source_index.items() if entry["position"] < len(chunks)}
    request_text = "\n".join([state.get("topic") or "", state.get("context") or ""])
    groups = review_groups(len(sentences))
    result: dict[str, Any] = {"outcome": "not_reviewed", "issues": [], "invalid": [], "records": [],
                              "groups": len(groups), "model": REVIEW_MODEL, "input_tokens": 0, "output_tokens": 0}

    reviews: list[Review | None] = []
    errors: list[str] = []
    with trace_calls() as calls:
        if groups:
            with ThreadPoolExecutor(max_workers=len(groups)) as pool:
                # copy_context: each worker appends to this trace's list and logs usage as the caller.
                futures = [pool.submit(contextvars.copy_context().run, _review_group, state, sentences, group)
                           for group in groups]
            for number, future in enumerate(futures, 1):
                exc = future.exception()
                if exc is None:
                    reviews.append(future.result())
                elif isinstance(exc, (StructuredOutputError, anthropic.APIError)):
                    reviews.append(None)
                    errors.append(f"group {number} of {len(groups)}: {_failure(exc)}")
                else:
                    raise exc
    result["input_tokens"] = sum(c["input_tokens"] for c in calls)
    result["output_tokens"] = sum(c["output_tokens"] for c in calls)
    if errors:
        result["error"] = "; ".join(errors)
        logger.warning("review: not reviewed (%s)", result["error"])
        return result

    merged = [record for review in reviews for record in review.sentences]
    result["records"] = [record.model_dump(exclude_defaults=True) for record in merged]
    coverage = _coverage_error([record.sentence for record in merged], len(sentences))
    if coverage:
        result["error"] = coverage
        logger.warning("review: not reviewed (%s)", coverage)
        return result

    def invalid(record_sentence: int, reason: str, what: Any) -> None:
        text = sentences[record_sentence - 1][1].text if 1 <= record_sentence <= len(sentences) else ""
        result["invalid"].append({"sentence": record_sentence - 1, "text": text, "reason": reason, "record": what})

    usable_records, placed = [], []
    for record in sorted(merged, key=lambda r: r.sentence):
        sentence = sentences[record.sentence - 1]
        reason = _invalid_reason(record, source_texts, request_text)
        if reason:
            invalid(record.sentence, reason, record.model_dump(exclude_defaults=True))
            continue
        usable = record.model_dump()
        problem = _detail_problem(record, sentence[1].text, source_texts, request_text)
        if problem:
            invalid(record.sentence, f"invalid_detail: {problem}", usable.pop("detail_change"))
            usable["detail_change"] = None
        if record.unsupported_part and not is_verbatim_span(record.unsupported_part, sentence[1].text):
            invalid(record.sentence, "invalid_unsupported_part: not_in_the_sentence", record.unsupported_part)
            usable["unsupported_part"] = None
        usable_records.append(usable)
        placed.append((record.sentence - 1, sentence))
    for issue in derive_issues(usable_records, [sentence for _, sentence in placed], source_index):
        result["issues"].append({**issue, "sentence": placed[issue["sentence"]][0]})

    for group, review in zip(groups, reviews):
        for note in review.ai_rhythm:
            if note.sentence not in group:
                invalid(note.sentence, "rhythm_sentence_outside_the_group", note.model_dump())
                continue
            span_position, sentence = sentences[note.sentence - 1]
            result["issues"].append({"type": "ai_rhythm", "sentence": note.sentence - 1, "span": span_position,
                                     "text": sentence.text, "sources": [], "evidence": None, "detail": {"why": note.why}})
    result["issues"].sort(key=lambda issue: issue["sentence"])
    result["outcome"] = "issues" if result["issues"] else "clean"
    if result["invalid"]:
        logger.warning("review: %d item(s) failed validation: %s",
                       len(result["invalid"]), [i["reason"] for i in result["invalid"]])
    return result
