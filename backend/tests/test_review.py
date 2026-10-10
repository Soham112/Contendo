"""The structured review (agents/review_agent.py): what it sends, how the
answer is validated, and what counts as reviewed. The model reports one record
of observations per sentence; the verdicts are derived in code
(tests/test_review_rules.py). Whether the model's observations are right is
measured on real calls (evals/fixtures/review_cases.jsonl), not here."""

import json

import pytest

from tests.checks_fixtures import PRICING, SURVEY
from tests.generation_fixtures import PROFILE, make_state
from tests.length_fixtures import _cut_off
from tests.review_fixtures import record, review_reply

MARKED = ("Average revenue per account fell 4 percent. [[S1]] That is a fair trade. [[V]]\n\n"
          "About 41 percent of teams skip reviews. [[S2]] You asked about pricing. [[R]] No marker here.")
REVIEW_MODEL = "claude-sonnet-4-6"
FIELDS = ["sentence", "content", "stated_as", "supported_by", "evidence", "detail_differs", "differing_detail",
          "presented_as", "links_cause_or_sequence", "link_sources", "link_stated_by", "off_topic"]


def _state(marked: str = MARKED, chunks=(PRICING, SURVEY), **overrides) -> dict:
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from utils.frames import build_sources_block

    chunks = list(chunks)
    state = make_state(chunks, archetype="general", current_draft=marked,
                       source_index=build_sources_block(chunks, PROFILE).index, **overrides)
    return finalise_draft_node(strip_draft_node(state))


def _review(claude, changes=None, *, rhythm=(), count=5, state=None) -> dict:
    """Review MARKED (five sentences) with a reply of benign records, changed as given."""
    from agents.review_agent import review_post

    claude.queue(review_reply(count, changes or {}, rhythm))
    return review_post(state or _state())


# --- The call ---------------------------------------------------------------------

def test_the_review_is_one_structured_sonnet_call_that_changes_nothing(claude):
    from agents.review_agent import review_post

    state = _state()
    before = json.dumps(state, sort_keys=True, default=str)
    claude.queue(review_reply(5))

    result = review_post(state)

    [call] = claude.calls
    assert call["model"] == REVIEW_MODEL and call["tool_choice"] == {"type": "tool", "name": "record_review"}
    assert json.dumps(state, sort_keys=True, default=str) == before
    assert (result["outcome"], result["issues"], result["invalid"]) == ("clean", [], [])
    assert (result["model"], result["input_tokens"], result["output_tokens"]) == (REVIEW_MODEL, 10, 10)
    assert [r["sentence"] for r in result["records"]] == [1, 2, 3, 4, 5]


def test_the_prompt_shows_the_sources_as_data_and_the_post_as_numbered_sentences_with_citations(claude):
    from utils.frames import PERSPECTIVES, SOURCES_ARE_DATA_RULE, build_sources_block

    _review(claude, state=_state(topic="Pricing experiments", context="For founders"))

    prompt = claude.calls[0]["messages"][-1]["content"]
    assert build_sources_block([PRICING, SURVEY], PROFILE).text in prompt
    assert SOURCES_ARE_DATA_RULE in prompt
    assert PERSPECTIVES["mixed"] in prompt
    assert "Topic: Pricing experiments" in prompt and "Additional context: For founders" in prompt
    assert f"Author: {PROFILE['name']}, {PROFILE['role']}" in prompt
    numbered = prompt[prompt.index("<post>") + 7:prompt.index("</post>")].strip().splitlines()
    assert numbered == [
        "1. [S1] Average revenue per account fell 4 percent.",
        "2. [V] That is a fair trade.",
        "3. [S2] About 41 percent of teams skip reviews.",
        "4. [R] You asked about pricing.",
        "5. [none] No marker here.",
    ]


def test_the_prompt_never_shows_the_authors_bio_opinions_or_samples(claude):
    _review(claude)

    prompt = claude.calls[0]["messages"][-1]["content"]
    assert PROFILE["bio"] not in prompt and PROFILE["opinions"][0] not in prompt
    assert PROFILE["writing_samples"][0] not in prompt


@pytest.mark.parametrize("event,expected", [
    ({"status": "cited", "source": "S1", "quote": "Early meetings were me presenting slides for an hour.", "line": "x"},
     'source S1, the sentence "Early meetings were me presenting slides for an hour."'),
    ({"status": "none", "source": None, "quote": None, "line": "EVENT: none"}, "found no event"),
])
def test_the_prompt_says_which_event_the_writer_named(claude, event, expected):
    state = _state()
    state["event"] = event
    _review(claude, state=state)

    assert expected in claude.calls[0]["messages"][-1]["content"]


def test_the_answer_is_observations_in_the_agreed_order_with_no_verdict_field():
    from agents.review_agent import Review, RhythmNote, SentenceRecord

    schema = SentenceRecord.model_json_schema()
    assert list(schema["properties"]) == FIELDS
    assert not {"type", "why", "excluded_by", "verdict", "issue"} & set(schema["properties"])
    assert list(Review.model_json_schema()["properties"]) == ["sentences", "ai_rhythm"]
    assert list(RhythmNote.model_json_schema()["properties"]) == ["sentence", "why"]


def test_every_field_and_every_value_is_described_in_the_prompt_without_quoted_phrases():
    from typing import get_args

    from agents.review_agent import REVIEW_PROMPT, Content, PresentedAs, StatedAs

    fields_part = REVIEW_PROMPT.split("Fill the fields of each entry in this order.", 1)[1]
    for field in FIELDS:
        assert f"\n{field}\n" in fields_part
    for value in (*get_args(Content), *get_args(StatedAs), *get_args(PresentedAs)):
        assert f"\n- {value}: " in fields_part or f"\n- {value}:" in fields_part
    assert '"' not in fields_part and "“" not in fields_part       # described, never quoted phrases
    assert len(get_args(Content)) == 9


def test_the_output_budget_grows_with_the_post_and_stays_within_the_ceiling(claude):
    from agents.review_agent import review_max_tokens
    from llm.client import MAX_NON_STREAMING_OUTPUT_TOKENS

    _review(claude)

    assert claude.calls[0]["max_tokens"] == review_max_tokens(5)
    assert review_max_tokens(5) < review_max_tokens(40) <= MAX_NON_STREAMING_OUTPUT_TOKENS
    assert review_max_tokens(10_000) == MAX_NON_STREAMING_OUTPUT_TOKENS


# --- Issues come from the rules ---------------------------------------------------

def test_issues_are_derived_from_the_records_and_say_which_sentence_and_span(claude):
    result = _review(claude, {
        3: dict(content="fact_or_event", stated_as="fact", supported_by=["S2"], presented_as="neutral",
                evidence="41 percent of teams skip reviews", detail_differs=True, differing_detail="41 against 14"),
        5: dict(content="fact_or_event", stated_as="fact", presented_as="neutral"),
    })

    assert result["outcome"] == "issues" and result["invalid"] == []
    assert [(i["type"], i["sentence"], i["span"], i["text"]) for i in result["issues"]] == [
        ("changed_detail", 2, 2, "About 41 percent of teams skip reviews."),
        ("not_in_sources", 4, 4, "No marker here."),
    ]
    assert result["issues"][0]["evidence"] == "41 percent of teams skip reviews"


def test_rhythm_notes_become_ai_rhythm_issues(claude):
    result = _review(claude, rhythm=[{"sentence": 2, "why": "A slogan-like closer."}])

    assert [(i["type"], i["sentence"], i["text"]) for i in result["issues"]] == [("ai_rhythm", 1, "That is a fair trade.")]
    assert result["outcome"] == "issues"


def test_a_rhythm_note_on_a_sentence_that_does_not_exist_is_invalid(claude):
    result = _review(claude, rhythm=[{"sentence": 9, "why": "x"}])

    assert result["outcome"] == "clean"
    assert [i["reason"] for i in result["invalid"]] == ["rhythm_sentence_out_of_range"]


# --- Every sentence, exactly once ---------------------------------------------------

@pytest.mark.parametrize("numbers,problem", [
    ([1, 2, 3, 4], "missing [5]"),
    ([1, 2, 4, 5], "missing [3]"),
    ([1, 2, 2, 3, 4, 5], "repeated [2]"),
    ([1, 2, 3, 4, 5, 6], "unknown [6]"),
    ([0, 1, 2, 3, 4, 5], "unknown [0]"),
    ([], "missing [1, 2, 3, 4, 5]"),
])
def test_records_that_do_not_cover_every_sentence_exactly_once_mean_not_reviewed(claude, numbers, problem):
    from agents.review_agent import review_post

    claude.queue(json.dumps({"sentences": [record(n) for n in numbers], "ai_rhythm": []}))

    result = review_post(_state())

    assert result["outcome"] == "not_reviewed" and result["issues"] == []
    assert result["error"].startswith("sentence_coverage") and problem in result["error"]
    assert len(result["records"]) == len(numbers)                # kept for the trace


def test_records_out_of_order_are_still_matched_to_their_sentences(claude):
    from agents.review_agent import review_post

    records = [record(n) for n in (5, 3, 1, 2, 4)]
    records[0].update(content="fact_or_event", stated_as="fact", presented_as="neutral")     # sentence 5
    claude.queue(json.dumps({"sentences": records, "ai_rhythm": []}))

    result = review_post(_state())

    assert [(i["type"], i["sentence"], i["text"]) for i in result["issues"]] == [("not_in_sources", 4, "No marker here.")]


# --- Invalid records ----------------------------------------------------------------

FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")


@pytest.mark.parametrize("changes,reason", [
    (dict(supported_by=["S9"]), "unknown_source"),
    (dict(supported_by=["S1"], link_sources=["S1", "S7"], links_cause_or_sequence=True), "unknown_source"),
    (dict(supported_by=["S1"], link_stated_by=["S8"]), "unknown_source"),
    (dict(supported_by=["S1"], link_sources=["request"]), "request_is_not_a_link_source"),
    (dict(supported_by=["S1"], evidence="revenue per account fell 5 percent"), "evidence_not_in_source"),     # not what it says
    (dict(supported_by=["S1"], evidence="revenue per account fell 4 per"), "evidence_not_in_source"),         # stops inside a word
    (dict(supported_by=["S1"], evidence="41 percent of teams skip reviews"), "evidence_not_in_source"),       # in S2, S1 named
    (dict(supported_by=[], evidence="average revenue per account fell 4 percent"), "evidence_without_source"),
    (dict(supported_by=["request"], evidence="average revenue per account fell 4 percent"), "evidence_not_in_source"),
])
def test_a_record_that_fails_validation_is_reported_and_nothing_is_derived_from_it(claude, changes, reason):
    # Every one of these records would otherwise give an issue: a changed detail on sentence 1.
    result = _review(claude, {1: {**FACT, "detail_differs": True, **changes}})

    assert result["outcome"] == "clean" and result["issues"] == []
    [invalid] = result["invalid"]
    assert invalid["reason"].startswith(reason)
    assert (invalid["sentence"], invalid["text"]) == (0, "Average revenue per account fell 4 percent.")
    assert invalid["record"]["sentence"] == 1


@pytest.mark.parametrize("evidence", [
    "average revenue per account fell 4 percent",
    "AVERAGE revenue per account   fell\n4 percent",                  # case and whitespace may differ
])
def test_evidence_copied_word_for_word_from_a_supporting_source_is_accepted(claude, evidence):
    result = _review(claude, {1: {**FACT, "supported_by": ["S1"], "evidence": evidence, "detail_differs": True}})

    assert result["invalid"] == []
    assert [i["type"] for i in result["issues"]] == ["changed_detail"]


def test_evidence_for_the_request_is_checked_against_the_topic_and_context(claude):
    state = _state(topic="What 41 investor meetings taught me", context="We closed in March")
    changes = {4: {**FACT, "supported_by": ["request"], "evidence": "41 investor meetings"}}

    assert _review(claude, changes, state=state)["invalid"] == []
    changes[4]["evidence"] = "42 investor meetings"
    assert [i["reason"] for i in _review(claude, changes, state=state)["invalid"]] == ["evidence_not_in_source"]


def test_an_invalid_record_does_not_stop_the_other_sentences_being_judged(claude):
    result = _review(claude, {
        1: {**FACT, "supported_by": ["S9"]},
        5: FACT,
    })

    assert [i["reason"] for i in result["invalid"]] == ["unknown_source: ['S9']"]
    assert [(i["type"], i["sentence"]) for i in result["issues"]] == [("not_in_sources", 4)]
    assert result["outcome"] == "issues"


@pytest.mark.parametrize("field,value", [
    ("content", "sounds_off"), ("stated_as", "maybe"), ("presented_as", "the_author"),
    ("detail_differs", "unsure"), ("off_topic", None),
])
def test_a_value_outside_the_schema_is_not_a_usable_answer(claude, field, value):
    from agents.review_agent import review_post

    bad = review_reply(5, {1: {field: value}})
    claude.queue(bad, bad)

    result = review_post(_state())

    assert result["outcome"] == "not_reviewed" and result["error"].startswith("invalid_output")


def test_an_answer_in_the_old_issue_list_shape_is_not_a_usable_answer(claude):
    from agents.review_agent import review_post

    old = json.dumps({"issues": [{"type": "not_in_sources", "sentence": 1, "sources": [], "why": "x"}]})
    claude.queue(old, old)

    assert review_post(_state())["outcome"] == "not_reviewed"


# --- Not reviewed -----------------------------------------------------------------

def test_a_truncated_answer_is_not_reviewed_and_never_clean(claude):
    from agents.review_agent import review_post

    claude.queue(_cut_off(), _cut_off())                           # complete_structured asks twice

    result = review_post(_state())

    assert (result["outcome"], result["error"]) == ("not_reviewed", "truncated")
    assert result["issues"] == [] and result["invalid"] == [] and result["records"] == []
    assert (result["input_tokens"], result["output_tokens"]) == (20, 4000)      # both attempts are counted


def test_an_answer_that_is_not_a_tool_call_is_not_reviewed(claude):
    from agents.review_agent import review_post

    claude.queue("The post looks fine to me.", "The post looks fine to me.")

    result = review_post(_state())

    assert result["outcome"] == "not_reviewed" and result["error"].startswith("invalid_output")


def test_a_failed_call_is_not_reviewed(claude):
    import anthropic
    import httpx

    from agents.review_agent import review_post

    def overloaded(kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    claude.respond_with(overloaded)

    result = review_post(_state())

    assert (result["outcome"], result["error"]) == ("not_reviewed", "api_error: InternalServerError")
    assert (result["input_tokens"], result["output_tokens"]) == (0, 0)


# --- Usage ------------------------------------------------------------------------

def test_the_reviews_calls_still_reach_a_trace_around_it(claude):
    from agents.review_agent import review_post
    from llm.client import trace_calls

    claude.queue(review_reply(5))
    with trace_calls() as outer:
        result = review_post(_state())

    assert [c["event_type"] for c in outer] == ["review"]
    assert (result["input_tokens"], result["output_tokens"]) == (outer[0]["input_tokens"], outer[0]["output_tokens"])
