"""The structured review (agents/review_agent.py): what it sends, how the
answers are merged and validated, and what counts as reviewed. The model
reports one compact record of observations per sentence and never sees the
citations; the verdicts are derived in code (tests/test_review_rules.py).
Whether the observations are right is measured on real calls
(evals/fixtures/review_cases.jsonl), not here."""

import json

import pytest

from tests.checks_fixtures import PRICING, SURVEY
from tests.generation_fixtures import PROFILE, make_state
from tests.length_fixtures import _cut_off
from tests.review_fixtures import answer_groups, assigned, record, review_reply

MARKED = ("Average revenue per account fell 4 percent. [[S1]] That is a fair trade. [[V]]\n\n"
          "About 41 percent of teams skip reviews. [[S2]] You asked about pricing. [[R]] No marker here.")
# Four sentences: one review group, so one call.
SHORT = ("Average revenue per account fell 4 percent. [[S1]] That is a fair trade. [[V]]\n\n"
         "About 41 percent of teams skip reviews. [[S2]] No marker here.")
REVIEW_MODEL = "claude-sonnet-4-6"
FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")


def _state(marked: str = MARKED, chunks=(PRICING, SURVEY), **overrides) -> dict:
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from utils.frames import build_sources_block

    chunks = list(chunks)
    state = make_state(chunks, archetype="general", current_draft=marked,
                       source_index=build_sources_block(chunks, PROFILE).index, **overrides)
    return finalise_draft_node(strip_draft_node(state))


def _long_state(count: int = 19) -> dict:
    """A post of `count` one-sentence view lines: several review groups."""
    return _state("\n\n".join(f"Plain sentence number {chr(96 + n)} of the post. [[V]]" for n in range(1, count + 1)))


def _review(claude, changes=None, *, rhythm=None, state=None, replace=None) -> dict:
    """Review a post (MARKED, five sentences, unless a state is given) with benign records changed as given."""
    from agents.review_agent import review_post

    answer_groups(claude, changes, rhythm, replace)
    return review_post(state or _state())


def _prompt(claude, call=0) -> str:
    return claude.calls[call]["messages"][-1]["content"]


# --- The call ---------------------------------------------------------------------

def test_a_short_post_is_one_structured_sonnet_call_that_changes_nothing(claude):
    state = _state(SHORT)
    before = json.dumps(state, sort_keys=True, default=str)

    result = _review(claude, state=state)

    [call] = claude.calls
    assert call["model"] == REVIEW_MODEL and call["tool_choice"] == {"type": "tool", "name": "record_review"}
    assert json.dumps(state, sort_keys=True, default=str) == before
    assert (result["outcome"], result["issues"], result["invalid"], result["groups"]) == ("clean", [], [], 1)
    assert (result["model"], result["input_tokens"], result["output_tokens"]) == (REVIEW_MODEL, 10, 10)
    assert [r["sentence"] for r in result["records"]] == [1, 2, 3, 4]


def test_the_reviewer_is_never_shown_the_citations(claude):
    _review(claude)

    prompt = _prompt(claude)
    numbered = prompt[prompt.index("<post>") + 7:prompt.index("</post>")].strip().splitlines()
    assert numbered == [
        "1. Average revenue per account fell 4 percent.",
        "2. That is a fair trade.",
        "3. About 41 percent of teams skip reviews.",
        "4. You asked about pricing.",
        "5. No marker here.",
    ]
    outside_sources = prompt[:prompt.index("<sources>")] + prompt[prompt.index("</sources>"):]
    for label in ("[S1]", "[S2]", "[V]", "[R]", "[none]", "[[", "citation"):
        assert label not in outside_sources, label


def test_the_prompt_shows_the_sources_as_data_the_author_and_the_request(claude):
    from utils.frames import PERSPECTIVES, SOURCES_ARE_DATA_RULE, build_sources_block

    _review(claude, state=_state(topic="Pricing experiments", context="For founders"))

    prompt = _prompt(claude)
    assert build_sources_block([PRICING, SURVEY], PROFILE).text in prompt
    assert SOURCES_ARE_DATA_RULE in prompt and PERSPECTIVES["mixed"] in prompt
    assert "Topic: Pricing experiments" in prompt and "Additional context: For founders" in prompt
    assert f"Author: {PROFILE['name']}, {PROFILE['role']}" in prompt
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

    assert expected in _prompt(claude)


def test_the_review_call_uses_the_one_prompt_builder():
    import agents.review_agent as review_agent
    import agents.review_prompt as review_prompt

    assert review_agent.build_review_prompt is review_prompt.build_review_prompt
    assert not hasattr(review_agent, "REVIEW_PROMPT")              # the text lives in one place


def test_a_record_needs_four_fields_and_has_no_verdict_field():
    from agents.review_agent import Review, SentenceRecord

    schema = SentenceRecord.model_json_schema()
    assert schema["required"] == ["sentence", "content", "stated_as", "presented_as"]
    assert list(schema["properties"]) == ["sentence", "content", "stated_as", "presented_as", "supported_by", "evidence",
                                          "unsupported_part", "detail_change", "link", "off_topic"]
    assert not {"type", "why", "excluded_by", "verdict", "detail_differs", "links_cause_or_sequence"} & set(schema["properties"])
    assert list(Review.model_json_schema()["properties"]) == ["sentences", "ai_rhythm"]


def test_omitted_fields_take_their_defaults():
    from agents.review_agent import SentenceRecord

    bare = SentenceRecord.model_validate(record(3))

    assert (bare.supported_by, bare.evidence, bare.unsupported_part, bare.detail_change, bare.link, bare.off_topic) == (
        [], None, None, None, None, False)
    assert bare.model_dump(exclude_defaults=True) == record(3)


def test_every_field_and_every_value_is_described_in_the_prompt_without_quoted_phrases():
    from typing import get_args

    from agents.review_agent import Content, PresentedAs, SentenceRecord, StatedAs
    from agents.review_prompt import REVIEW_PROMPT

    fields_part = REVIEW_PROMPT.split("Always given:", 1)[1]
    for field in SentenceRecord.model_fields:
        assert f"\n{field}\n" in fields_part
    for value in (*get_args(Content), *get_args(StatedAs), *get_args(PresentedAs)):
        assert f"\n- {value}: " in fields_part
    assert '"' not in fields_part and "“" not in fields_part       # described, never quoted phrases


# --- Parallel groups --------------------------------------------------------------

@pytest.mark.parametrize("count", [1, 5, 6, 7, 12, 13, 19, 36, 37, 100])
def test_groups_cover_every_sentence_exactly_once_in_order(count):
    from agents.review_agent import MAX_REVIEW_GROUPS, SENTENCES_PER_GROUP, review_groups

    groups = review_groups(count)

    assert [n for group in groups for n in group] == list(range(1, count + 1))
    assert len(groups) <= MAX_REVIEW_GROUPS
    assert max(len(g) for g in groups) - min(len(g) for g in groups) <= 1
    if count <= SENTENCES_PER_GROUP * MAX_REVIEW_GROUPS:
        assert max(len(g) for g in groups) <= SENTENCES_PER_GROUP
    assert review_groups(0) == []


def test_a_long_post_is_reviewed_by_one_call_per_group_and_the_answers_are_merged(claude):
    from agents.review_agent import group_max_tokens, review_groups

    state = _long_state(19)
    result = _review(claude, {4: FACT, 17: FACT}, rhythm={12: {"sentence": 12, "why": "A slogan."}}, state=state)

    groups = review_groups(19)
    assert [len(g) for g in groups] == [4, 4, 4, 4, 3]
    assert len(claude.calls) == len(groups) == result["groups"] == 5
    assert sorted((assigned(c)[0], assigned(c)[-1]) for c in claude.calls) == [(g[0], g[-1]) for g in groups]
    assert sorted(c["max_tokens"] for c in claude.calls) == sorted(group_max_tokens(len(g)) for g in groups)
    assert [r["sentence"] for r in result["records"]] == list(range(1, 20))
    assert [(i["type"], i["sentence"]) for i in result["issues"]] == [("not_in_sources", 3), ("ai_rhythm", 11), ("not_in_sources", 16)]
    assert (result["input_tokens"], result["output_tokens"]) == (50, 50)          # every group's call is counted


def test_every_group_sees_the_whole_post_and_the_same_text_up_to_its_assignment(claude):
    _review(claude, state=_long_state(19))

    prompts = [c["messages"][-1]["content"] for c in claude.calls]
    shared = {p[:p.index("Your assignment:")] for p in prompts}
    assert len(shared) == 1
    assert "19. Plain sentence number s of the post." in shared.pop()


@pytest.mark.parametrize("failure,error", [
    (_cut_off(), "truncated"),
    ("I could not review these.", "invalid_output"),
])
def test_one_group_that_fails_or_is_cut_off_means_the_whole_post_was_not_reviewed(claude, failure, error):
    result = _review(claude, {4: FACT}, state=_long_state(19), replace={5: failure})      # the group starting at sentence 5

    assert result["outcome"] == "not_reviewed" and result["issues"] == [] and result["records"] == []
    assert result["error"].startswith("group 2 of 5: " + error)
    assert result["groups"] == 5


def test_an_api_error_in_one_group_means_not_reviewed(claude):
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    overloaded = anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    result = _review(claude, state=_long_state(19), replace={9: overloaded})

    assert (result["outcome"], result["error"]) == ("not_reviewed", "group 3 of 5: api_error: InternalServerError")


@pytest.mark.parametrize("reply_numbers,problem", [
    ([5, 6, 7], "missing [8]"),                             # a gap: the group left one of its sentences out
    ([5, 6, 7, 8, 9], "repeated [9]"),                      # an overlap: it also recorded the next group's first sentence
    ([5, 6, 7, 8, 8], "repeated [8]"),
    ([5, 6, 7, 8, 25], "unknown [25]"),
])
def test_the_merged_coverage_check_catches_a_gap_or_an_overlap_between_groups(claude, reply_numbers, problem):
    result = _review(claude, state=_long_state(19), replace={5: review_reply(reply_numbers)})

    assert result["outcome"] == "not_reviewed"
    assert result["error"].startswith("sentence_coverage") and problem in result["error"]
    assert len(result["records"]) == 15 + len(reply_numbers)          # kept for the trace


def test_a_rhythm_note_for_a_sentence_outside_the_group_is_invalid(claude):
    note = {"sentence": 2, "why": "A slogan."}
    reply = json.dumps({"sentences": [record(n) for n in range(5, 9)], "ai_rhythm": [note]})

    result = _review(claude, state=_long_state(19), replace={5: reply})

    assert result["outcome"] == "clean"
    assert [(i["reason"], i["record"]) for i in result["invalid"]] == [("rhythm_sentence_outside_the_group", note)]


def test_the_group_budget_grows_with_its_sentences_and_stays_within_the_ceiling():
    from agents.review_agent import group_max_tokens
    from llm.client import MAX_NON_STREAMING_OUTPUT_TOKENS

    assert group_max_tokens(1) < group_max_tokens(6) < group_max_tokens(17) <= MAX_NON_STREAMING_OUTPUT_TOKENS
    assert group_max_tokens(100_000) == MAX_NON_STREAMING_OUTPUT_TOKENS


# --- Issues come from the rules, and wrong_citation from the trace's citation --------------

def test_issues_are_derived_from_the_records_and_say_which_sentence_and_span(claude):
    result = _review(claude, {
        3: dict(**FACT, supported_by=["S2"], evidence="41 percent of teams skip reviews",
                detail_change={"source_words": "41 percent", "post_words": "About 41 percent"}),
        5: FACT,
    })

    assert result["outcome"] == "issues" and result["invalid"] == []
    assert [(i["type"], i["sentence"], i["span"], i["text"]) for i in result["issues"]] == [
        ("changed_detail", 2, 2, "About 41 percent of teams skip reviews."),
        ("not_in_sources", 4, 4, "No marker here."),
    ]


def test_wrong_citation_comes_from_the_drafts_citation_and_what_the_model_found(claude):
    # The model reports the same thing for sentences 1 (cited S1), 2 (cited as a view) and 5 (not cited):
    # a fact that S1 states. Only the two whose own citation does not point at S1 are wrong citations.
    found = dict(**FACT, supported_by=["S1"], evidence="average revenue per account fell 4 percent")

    result = _review(claude, {1: found, 2: found, 5: found})

    assert [(i["type"], i["sentence"]) for i in result["issues"]] == [("wrong_citation", 1), ("wrong_citation", 4)]
    assert [i["detail"]["cited"] for i in result["issues"]] == ["view", "uncited"]


def test_rhythm_notes_become_ai_rhythm_issues(claude):
    result = _review(claude, rhythm={2: {"sentence": 2, "why": "A slogan-like closer."}})

    assert [(i["type"], i["sentence"], i["text"]) for i in result["issues"]] == [("ai_rhythm", 1, "That is a fair trade.")]


# --- detail_change: both sides quoted, and really different -----------------------------

S2_FACT = dict(**FACT, supported_by=["S2"], evidence="41 percent of teams skip reviews")


@pytest.mark.parametrize("change", [
    {"source_words": "41 percent", "post_words": "About 41 percent"},
    {"source_words": "41 percent of teams", "post_words": "teams"},
    {"source_words": "skip reviews", "post_words": "skip"},
])
def test_a_detail_change_quoting_both_sides_with_a_real_difference_is_accepted(claude, change):
    result = _review(claude, {3: {**S2_FACT, "detail_change": change}})

    assert result["invalid"] == []
    [issue] = result["issues"]
    assert (issue["type"], issue["evidence"], issue["detail"]) == ("changed_detail", change["source_words"], change)


@pytest.mark.parametrize("change,problem", [
    ({"source_words": "14 percent", "post_words": "41 percent"}, "source_words_not_in_a_supporting_source"),      # invented
    ({"source_words": "fell 4 percent", "post_words": "41 percent"}, "source_words_not_in_a_supporting_source"),  # in S1, not S2
    ({"source_words": "41 percent", "post_words": "forty percent"}, "post_words_not_in_the_sentence"),
    ({"source_words": "41 percent", "post_words": "omits locations"}, "post_words_not_in_the_sentence"),
    ({"source_words": "41 percent", "post_words": "41 percent"}, "same_wording"),
    ({"source_words": "41 percent of teams", "post_words": "41 Percent  of teams"}, "same_wording"),
])
def test_a_detail_change_that_fails_its_checks_gives_no_changed_detail_and_is_reported(claude, change, problem):
    result = _review(claude, {3: {**S2_FACT, "detail_change": change}})

    assert result["issues"] == [] and result["outcome"] == "clean"
    [invalid] = result["invalid"]
    assert invalid["reason"] == f"invalid_detail: {problem}"
    assert (invalid["sentence"], invalid["record"]) == (2, change)


@pytest.mark.parametrize("source_text,post,change,accepted", [
    ("The form had nine steps.", "The form had 9 steps. [[S1]]", {"source_words": "nine steps", "post_words": "9 steps"}, False),
    ("What did not help: apps.", "What didn't help: apps. [[S1]]", {"source_words": "did not help", "post_words": "didn't help"}, False),
    ("Early meetings were slides.", "My first board meetings were slides. [[S1]]",
     {"source_words": "Early meetings", "post_words": "first board meetings"}, True),
])
def test_equivalent_forms_are_not_a_detail_change_and_a_real_difference_is(claude, source_text, post, change, accepted):
    state = _state(post, chunks=[{**PRICING, "text": source_text}])

    result = _review(claude, {1: dict(**FACT, supported_by=["S1"], evidence=source_text, detail_change=change)}, state=state)

    assert [i["type"] for i in result["issues"]] == (["changed_detail"] if accepted else [])
    assert [i["reason"] for i in result["invalid"]] == ([] if accepted else ["invalid_detail: same_wording"])


def test_an_invalid_detail_change_leaves_the_rest_of_the_record_in_force(claude):
    # Sentence 2 is cited as a view; the model found that S1 states it. The bad detail_change is dropped, the wrong citation stays.
    result = _review(claude, {2: dict(**FACT, supported_by=["S1"], evidence="average revenue per account fell 4 percent",
                                      detail_change={"source_words": "fell 9 percent", "post_words": "fair trade"})})

    assert [i["type"] for i in result["issues"]] == ["wrong_citation"]
    assert [i["reason"] for i in result["invalid"]] == ["invalid_detail: source_words_not_in_a_supporting_source"]


# --- unsupported_part: words of the sentence ---------------------------------------

def test_an_unsupported_part_copied_from_the_sentence_gives_not_in_sources(claude):
    result = _review(claude, {1: dict(**FACT, supported_by=["S1"], evidence="average revenue per account fell 4 percent",
                                      unsupported_part="Average revenue per account")})

    [issue] = result["issues"]
    assert (issue["type"], issue["sentence"], issue["detail"]["unsupported_part"]) == ("not_in_sources", 0, "Average revenue per account")
    assert result["invalid"] == []


@pytest.mark.parametrize("part", ["because of the price rise", "revenue per acc", "fell 5 percent"])
def test_an_unsupported_part_that_is_not_words_of_the_sentence_is_dropped_and_reported(claude, part):
    result = _review(claude, {1: dict(**FACT, supported_by=["S1"], evidence="average revenue per account fell 4 percent",
                                      unsupported_part=part)})

    assert result["issues"] == []
    assert [(i["reason"], i["record"]) for i in result["invalid"]] == [("invalid_unsupported_part: not_in_the_sentence", part)]


# --- Every sentence, exactly once (one group) ------------------------------------------

@pytest.mark.parametrize("numbers,problem", [
    ([1, 2, 3], "missing [4]"), ([1, 2, 2, 3, 4], "repeated [2]"), ([1, 2, 3, 4, 5], "unknown [5]"),
    ([], "missing [1, 2, 3, 4]"),
])
def test_records_that_do_not_cover_every_sentence_exactly_once_mean_not_reviewed(claude, numbers, problem):
    result = _review(claude, state=_state(SHORT), replace={1: review_reply(numbers)})

    assert result["outcome"] == "not_reviewed" and result["issues"] == []
    assert result["error"].startswith("sentence_coverage") and problem in result["error"]


def test_records_out_of_order_are_still_matched_to_their_sentences(claude):
    result = _review(claude, state=_state(SHORT), replace={1: review_reply([4, 3, 1, 2], {4: FACT})})

    assert [(i["type"], i["sentence"], i["text"]) for i in result["issues"]] == [("not_in_sources", 3, "No marker here.")]


# --- Invalid records ----------------------------------------------------------------

CHANGE = {"source_words": "fell 4 percent", "post_words": "Average"}


@pytest.mark.parametrize("changes,reason", [
    (dict(supported_by=["S9"]), "unknown_source"),
    (dict(supported_by=["S1"], link={"sources": ["S1", "S7"]}), "unknown_source"),
    (dict(supported_by=["S1"], link={"sources": ["S1", "S2"], "stated_by": ["S8"]}), "unknown_source"),
    (dict(supported_by=["S1"], link={"sources": ["request", "S1"]}), "request_is_not_a_link_source"),
    (dict(supported_by=["S1"], evidence="revenue per account fell 5 percent"), "evidence_not_in_source"),     # not what it says
    (dict(supported_by=["S1"], evidence="revenue per account fell 4 per"), "evidence_not_in_source"),         # stops inside a word
    (dict(supported_by=["S1"], evidence="41 percent of teams skip reviews"), "evidence_not_in_source"),       # in S2, S1 named
    (dict(evidence="average revenue per account fell 4 percent"), "evidence_without_source"),
])
def test_a_record_that_fails_validation_is_reported_and_nothing_is_derived_from_it(claude, changes, reason):
    # Each of these records would otherwise give an issue: a changed detail on sentence 1.
    result = _review(claude, {1: {**FACT, "detail_change": CHANGE, **changes}})

    assert result["outcome"] == "clean" and result["issues"] == []
    [invalid] = result["invalid"]
    assert invalid["reason"].startswith(reason)
    assert (invalid["sentence"], invalid["text"]) == (0, "Average revenue per account fell 4 percent.")


def test_evidence_may_differ_in_case_and_whitespace_only(claude):
    ok = _review(claude, {1: {**FACT, "supported_by": ["S1"], "evidence": "AVERAGE revenue per account   fell\n4 percent"}})

    assert ok["invalid"] == [] and ok["outcome"] == "clean"


def test_evidence_for_the_request_is_checked_against_the_topic_and_context(claude):
    state = _state(topic="What 41 investor meetings taught me", context="We closed in March")
    changes = {4: {**FACT, "supported_by": ["request"], "evidence": "41 investor meetings"}}

    assert _review(claude, changes, state=state)["invalid"] == []
    changes[4]["evidence"] = "42 investor meetings"
    assert [i["reason"] for i in _review(claude, changes, state=state)["invalid"]] == ["evidence_not_in_source"]


def test_an_invalid_record_does_not_stop_the_other_sentences_being_judged(claude):
    result = _review(claude, {1: {**FACT, "supported_by": ["S9"]}, 5: FACT})

    assert [i["reason"] for i in result["invalid"]] == ["unknown_source: ['S9']"]
    assert [(i["type"], i["sentence"]) for i in result["issues"]] == [("not_in_sources", 4)]


@pytest.mark.parametrize("field,value", [
    ("content", "sounds_off"), ("stated_as", "maybe"), ("presented_as", "the_author"), ("off_topic", "unsure"),
    ("detail_change", {"source_words": "x"}), ("link", {"stated_by": ["S1"]}),
])
def test_a_value_outside_the_schema_is_not_a_usable_answer(claude, field, value):
    result = _review(claude, {1: {field: value}})

    assert result["outcome"] == "not_reviewed" and "invalid_output" in result["error"]


def test_a_record_missing_a_required_field_is_not_a_usable_answer(claude):
    incomplete = json.dumps({"sentences": [{"sentence": n, "content": "opinion"} for n in range(1, 5)]})

    result = _review(claude, state=_state(SHORT), replace={1: incomplete})

    assert result["outcome"] == "not_reviewed"


# --- Not reviewed, usage ----------------------------------------------------------------

def test_a_truncated_answer_is_not_reviewed_and_never_clean(claude):
    result = _review(claude, state=_state(SHORT), replace={1: _cut_off()})

    assert (result["outcome"], result["error"]) == ("not_reviewed", "group 1 of 1: truncated")
    assert result["issues"] == [] and result["invalid"] == [] and result["records"] == []
    assert (result["input_tokens"], result["output_tokens"]) == (20, 4000)      # both attempts are counted


def test_an_empty_post_makes_no_call_and_is_clean(claude):
    from agents.review_agent import review_post

    result = review_post(_state("```\ncode only\n```"))

    assert claude.calls == [] and (result["outcome"], result["groups"]) == ("clean", 0)


def test_the_reviews_calls_from_every_group_reach_a_trace_around_it(claude):
    from agents.review_agent import review_post
    from llm.client import trace_calls

    answer_groups(claude)
    with trace_calls() as outer:
        result = review_post(_long_state(19))

    assert [c["event_type"] for c in outer] == ["review"] * 5
    assert result["input_tokens"] == sum(c["input_tokens"] for c in outer)
