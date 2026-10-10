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

A second review (of variant B's redraft) does not send the sentences the
redraft left alone: a sentence with the same text and the same citation as a
sentence of the first draft takes that sentence's record, and only the new or
changed sentences are sent, grouped the same way.

The prompt is built in agents/review_prompt.py; this file holds the call, the
merge and the two graph nodes of variant B (review_node, review_redraft_node);
the validation is in pipeline/review_validation.py. What an issue leads to is
decided in pipeline/redraft.py.
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
from pipeline.review_rules import derive_issues
from pipeline.review_validation import coverage_error, validate_records
from pipeline.state import PipelineState
from utils.citations import Span
from utils.frames import chunk_field
from utils.sentences import split_spans

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


def _same_sentence_key(text: str, basis: str, sources) -> tuple:
    """What makes a sentence of the redraft the same as one of the first draft:
    its text, whitespace aside, and its citation."""
    return " ".join(text.split()), basis, tuple(sources)


def _reusable(previous: dict[str, Any], sentences: list[tuple[int, Span]]) -> dict[int, dict]:
    """sentence number in this post -> {record, rhythm} taken from the previous
    review, for each sentence that review already described. A sentence that
    occurs more than once is matched in order: the second occurrence here takes
    the second occurrence there, and one with no counterpart left is sent for
    review. A sentence the previous review left without a valid record
    (previous["unreviewed"]) is never reused: it is sent again."""
    unreviewed = set(previous["unreviewed"])
    records = {record["sentence"]: record for record in previous["records"]}
    rhythm: dict[int, list[str]] = {}
    for issue in previous["issues"]:
        if issue["type"] == "ai_rhythm":
            rhythm.setdefault(issue["sentence"] + 1, []).append(issue["detail"]["why"])
    earlier: dict[tuple, list[int]] = {}
    for number, sentence in enumerate(previous["sentences"], 1):
        if number - 1 in unreviewed:
            continue
        earlier.setdefault(_same_sentence_key(sentence["text"], sentence["basis"], sentence["sources"]), []).append(number)
    reuse = {}
    for number, (_, sentence) in enumerate(sentences, 1):
        left = earlier.get(_same_sentence_key(sentence.text, sentence.basis, sentence.sources))
        if left:
            was = left.pop(0)
            reuse[number] = {"record": {**records[was], "sentence": number}, "rhythm": rhythm.get(was, [])}
    return reuse


def _review_group(state: PipelineState, sentences: list[tuple[int, Span]], group: list[int]) -> Review:
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


def _run_groups(state: PipelineState, sentences: list[tuple[int, Span]],
                groups: list[list[int]]) -> tuple[list[Review | None], list[str], list[dict]]:
    """One call per group, concurrently: (each group's answer or None, why any
    failed, the calls made). An error that is not the model's or the API's is raised."""
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
    return reviews, errors, calls


def review_post(state: PipelineState, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Review the post in state. Changes nothing.

    previous: an earlier review_post result for an earlier draft of this post.
    A sentence it holds a valid record for, and that is unchanged here (same
    text after whitespace normalisation, same citation), takes that record and
    is not sent again.

    Returns {outcome, issues, invalid, unreviewed, records, sentences, reused,
    reviewed, groups, model, input_tokens, output_tokens} and, when the review
    did not happen, error:
      outcome     "clean" (the rules derived no issue), "issues", or
                  "not_reviewed": a group's call failed or its answer could not
                  be used, or the records do not cover every sentence sent
                  exactly once. Never treated as clean.
      issues      derived in code (pipeline.review_rules.derive_issues) from the
                  valid records, plus the ai_rhythm notes: {type, sentence, span,
                  text, sources, evidence, detail}; sentence is 0-based
      invalid     what failed validation, each with a reason
                  (pipeline.review_validation), and rhythm notes for a sentence
                  outside the group that gave them
      unreviewed  0-based sentences with no valid record: every sentence when
                  the review did not happen, else those whose whole record was invalid
      records     the model's observations, one per sentence, merged from the
                  groups and from the reused records
      sentences   the sentences as numbered, [{text, basis, sources}]
      reused, reviewed   sentences that took a previous record, and sentences sent
      groups      how many parallel calls made the review
    """
    sentences = post_sentences(state.get("citations") or [])
    source_index = state.get("source_index") or {}
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    source_texts = {sid: chunk_field(chunks[entry["position"]], "text") or chunk_field(chunks[entry["position"]], "content")
                    for sid, entry in source_index.items() if entry["position"] < len(chunks)}
    request_text = "\n".join([state.get("topic") or "", state.get("context") or ""])
    reuse = _reusable(previous, sentences) if previous else {}
    to_review = [number for number in range(1, len(sentences) + 1) if number not in reuse]
    groups = [[to_review[position - 1] for position in group] for group in review_groups(len(to_review))]
    result: dict[str, Any] = {
        "outcome": "not_reviewed", "issues": [], "invalid": [], "unreviewed": list(range(len(sentences))),
        "records": [],
        "sentences": [{"text": s.text, "basis": s.basis, "sources": list(s.sources)} for _, s in sentences],
        "reused": len(reuse), "reviewed": len(to_review),
        "groups": len(groups), "model": REVIEW_MODEL, "input_tokens": 0, "output_tokens": 0}

    reviews, errors, calls = _run_groups(state, sentences, groups)
    result["input_tokens"] = sum(c["input_tokens"] for c in calls)
    result["output_tokens"] = sum(c["output_tokens"] for c in calls)
    merged = [] if errors else [record for review in reviews for record in review.sentences]
    error = "; ".join(errors) or coverage_error([record.sentence for record in merged], to_review)
    if not errors:
        merged += [SentenceRecord(**kept["record"]) for kept in reuse.values()]
        result["records"] = [r.model_dump(exclude_defaults=True) for r in sorted(merged, key=lambda r: r.sentence)]
    if error:
        result["error"] = error
        logger.warning("review: not reviewed (%s)", error)
        return result

    usable, positions, result["invalid"] = validate_records(merged, sentences, source_texts, request_text)
    result["unreviewed"] = [position for position in range(len(sentences)) if position not in positions]
    for issue in derive_issues(usable, [sentences[position] for position in positions], source_index):
        result["issues"].append({**issue, "sentence": positions[issue["sentence"]]})

    notes = [(number, why) for number, kept in reuse.items() for why in kept["rhythm"]]
    for group, review in zip(groups, reviews):
        for note in review.ai_rhythm:
            if note.sentence in group:
                notes.append((note.sentence, note.why))
            else:
                text = sentences[note.sentence - 1][1].text if 1 <= note.sentence <= len(sentences) else ""
                result["invalid"].append({"sentence": note.sentence - 1, "text": text,
                                          "reason": "rhythm_sentence_outside_the_group", "record": note.model_dump()})
    for number, why in notes:
        span_position, sentence = sentences[number - 1]
        result["issues"].append({"type": "ai_rhythm", "sentence": number - 1, "span": span_position,
                                 "text": sentence.text, "sources": [], "evidence": None, "detail": {"why": why}})
    result["issues"].sort(key=lambda issue: issue["sentence"])
    result["outcome"] = "issues" if result["issues"] else "clean"
    if result["invalid"]:
        logger.warning("review: %d item(s) failed validation: %s",
                       len(result["invalid"]), [i["reason"] for i in result["invalid"]])
    return result


# ── Graph nodes (variant B) ───────────────────────────────────────────────────

def review_node(state: PipelineState) -> PipelineState:
    """Review the first draft: state["review_first"]."""
    state["review_first"] = review_post(state)
    return state


def review_redraft_node(state: PipelineState) -> PipelineState:
    """Review the redraft, sending only the sentences it changed or added:
    state["review_second"]."""
    state["review_second"] = review_post(state, previous=state["review_first"])
    return state
