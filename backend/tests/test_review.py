"""The structured review (agents/review_agent.py): what it sends, how every
returned issue is validated, and what counts as reviewed. Whether the model's
judgements are right is measured on real calls (evals/fixtures/review_cases.jsonl),
not here."""

import json

import pytest

from tests.checks_fixtures import PRICING, SURVEY
from tests.generation_fixtures import PROFILE, make_state
from tests.length_fixtures import _cut_off

MARKED = ("Average revenue per account fell 4 percent. [[S1]] That is a fair trade. [[V]]\n\n"
          "About 41 percent of teams skip reviews. [[S2]] You asked about pricing. [[R]] No marker here.")
REVIEW_MODEL = "claude-sonnet-4-6"


def _state(marked: str = MARKED, chunks=(PRICING, SURVEY), **overrides) -> dict:
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from utils.frames import build_sources_block

    chunks = list(chunks)
    state = make_state(chunks, archetype="general", current_draft=marked,
                       source_index=build_sources_block(chunks, PROFILE).index, **overrides)
    return finalise_draft_node(strip_draft_node(state))


def _review(claude, *issues, state=None) -> dict:
    from agents.review_agent import review_post

    claude.queue(json.dumps({"issues": list(issues)}))
    return review_post(state or _state())


def _issue(**fields) -> dict:
    return {"sentence": 1, "sources": ["S1"], "evidence": None,
            "analysis": "The source gives the figure; the post adds a cause.", "excluded_by": "none",
            "type": "not_in_sources", "why": "The source does not say this.", **fields}


# --- The call ---------------------------------------------------------------------

def test_the_review_is_one_structured_sonnet_call_that_changes_nothing(claude):
    from agents.review_agent import review_post

    state = _state()
    before = json.dumps(state, sort_keys=True, default=str)
    claude.queue(json.dumps({"issues": []}))

    result = review_post(state)

    [call] = claude.calls
    assert call["model"] == REVIEW_MODEL and call["tool_choice"] == {"type": "tool", "name": "record_review"}
    assert json.dumps(state, sort_keys=True, default=str) == before
    assert result == {"outcome": "clean", "issues": [], "excluded": [], "invalid": [], "model": REVIEW_MODEL,
                      "input_tokens": 10, "output_tokens": 10}


def test_the_prompt_shows_the_sources_as_data_and_the_post_as_numbered_sentences_with_citations(claude):
    from utils.frames import PERSPECTIVES, SOURCES_ARE_DATA_RULE, build_sources_block

    state = _state(topic="Pricing experiments", context="For founders")
    _review(claude, state=state)

    prompt = claude.calls[0]["messages"][-1]["content"]
    assert build_sources_block([PRICING, SURVEY], PROFILE).text in prompt
    assert SOURCES_ARE_DATA_RULE in prompt
    assert PERSPECTIVES["mixed"] in prompt
    assert "Topic: Pricing experiments" in prompt and "Additional context: For founders" in prompt
    numbered = prompt[prompt.index("<post>") + 7:prompt.index("</post>")].strip().splitlines()
    assert numbered == [
        "1. [S1] Average revenue per account fell 4 percent.",
        "2. [V] That is a fair trade.",
        "3. [S2] About 41 percent of teams skip reviews.",
        "4. [R] You asked about pricing.",
        "5. [none] No marker here.",
    ]


def test_a_multi_sentence_span_is_numbered_by_sentence_and_each_inherits_the_citation(claude):
    _review(claude, state=_state("Revenue fell 4 percent. Conversion rose. Logins too. [[S1]]"))

    prompt = claude.calls[0]["messages"][-1]["content"]
    assert "1. [S1] Revenue fell 4 percent.\n2. [S1] Conversion rose.\n3. [S1] Logins too." in prompt


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


SEVEN = ("not_in_sources", "changed_detail", "wrong_citation", "wrong_attribution",
         "cross_source_link", "off_topic", "ai_rhythm")


def test_there_are_seven_issue_types_each_defined_by_what_counts_and_never_by_a_phrase_list():
    from typing import get_args

    from agents.review_agent import REVIEW_PROMPT, IssueType

    assert get_args(IssueType) == SEVEN
    for issue_type in SEVEN:
        definition = REVIEW_PROMPT.split(f"\n{issue_type}\n", 1)[1].split("\n\n", 1)[0]
        assert "Counts:" in definition and "Does not count:" in definition
        assert '"' not in definition and "“" not in definition          # described, never quoted phrases


def test_the_answer_puts_the_reasoning_before_the_verdict():
    from typing import get_args

    from agents.review_agent import ExcludedBy, ReviewIssue

    assert list(ReviewIssue.model_json_schema()["properties"]) == [
        "sentence", "sources", "evidence", "analysis", "excluded_by", "type", "why"]
    assert list(ReviewIssue.model_fields) == ["sentence", "sources", "evidence", "analysis", "excluded_by", "type", "why"]
    assert get_args(ExcludedBy) == ("paraphrase", "opinion", "disclaimer", "authors_framing", "none")
    assert {"sentence", "analysis", "excluded_by", "type", "why"} <= set(ReviewIssue.model_json_schema()["required"])


def test_every_exclusion_the_answer_can_name_is_explained_in_the_prompt():
    from typing import get_args

    from agents.review_agent import REVIEW_PROMPT, ExcludedBy

    for exclusion in get_args(ExcludedBy):
        if exclusion != "none":
            assert f"\n- {exclusion}: " in REVIEW_PROMPT


# --- Validation -------------------------------------------------------------------

def test_a_valid_issue_counts_and_says_which_sentence_and_span(claude):
    result = _review(claude, _issue(type="changed_detail", sentence=3, sources=["S2"],
                                    evidence="41 percent of teams skip reviews", why="The share is changed."))

    assert result["outcome"] == "issues" and result["invalid"] == [] and result["excluded"] == []
    assert result["issues"] == [{
        "sentence": 2, "span": 2, "text": "About 41 percent of teams skip reviews.",
        "sources": ["S2"], "evidence": "41 percent of teams skip reviews",
        "analysis": "The source gives the figure; the post adds a cause.", "excluded_by": "none",
        "type": "changed_detail", "why": "The share is changed.",
    }]


@pytest.mark.parametrize("fields,reason", [
    ({"sentence": 0}, "sentence_out_of_range"),
    ({"sentence": 6}, "sentence_out_of_range"),
    ({"sentence": -2}, "sentence_out_of_range"),
    ({"sources": ["S9"]}, "unknown_source"),
    ({"sources": ["S1", "S7"]}, "unknown_source"),
    ({"type": "changed_detail", "evidence": None}, "evidence_required"),
    ({"type": "changed_detail", "evidence": "   "}, "evidence_required"),
    ({"evidence": "revenue per account fell 5 percent"}, "evidence_not_in_source"),            # not what the source says
    ({"evidence": "revenue per account fell 4 per"}, "evidence_not_in_source"),                # stops inside a word
    ({"evidence": "41 percent of teams skip reviews"}, "evidence_not_in_source"),              # in S2, but S1 is named
    ({"evidence": "average revenue per account fell 4 percent", "sources": []}, "evidence_without_source"),
    ({"type": "wrong_citation", "sources": []}, "source_required"),
])
def test_an_issue_that_fails_validation_is_kept_apart_with_the_reason_and_never_counts(claude, fields, reason):
    result = _review(claude, _issue(**fields))

    assert result["outcome"] == "clean" and result["issues"] == []
    [invalid] = result["invalid"]
    assert invalid["reason"].startswith(reason)
    assert invalid["type"] == fields.get("type", "not_in_sources")


@pytest.mark.parametrize("evidence", [
    "average revenue per account fell 4 percent",
    "AVERAGE revenue per account   fell\n4 percent",                  # case and whitespace may differ
    "Results: conversion improved from 13 to 16 percent; average revenue per account fell 4 percent; shared logins rose.",
])
def test_evidence_copied_word_for_word_from_a_named_source_is_accepted(claude, evidence):
    result = _review(claude, _issue(evidence=evidence))

    assert result["outcome"] == "issues" and result["issues"][0]["evidence"] == evidence.strip()


def test_evidence_may_come_from_any_of_the_sources_the_issue_names(claude):
    result = _review(claude, _issue(type="cross_source_link", sources=["S1", "S2"],
                                    evidence="41 percent of teams skip reviews"))

    assert result["outcome"] == "issues"


def test_an_issue_without_evidence_is_valid_unless_its_type_requires_it(claude):
    result = _review(claude, _issue(type="not_in_sources", sentence=2, sources=[]),
                     _issue(type="ai_rhythm", sentence=5, sources=[]),
                     _issue(type="wrong_citation", sentence=2, sources=["S1"]))

    assert [i["type"] for i in result["issues"]] == ["not_in_sources", "ai_rhythm", "wrong_citation"]


def test_valid_and_invalid_issues_are_separated_and_only_valid_ones_decide_the_outcome(claude):
    result = _review(claude, _issue(sentence=9), _issue(sentence=1), _issue(sources=["S4"]))

    assert result["outcome"] == "issues"
    assert [i["sentence"] for i in result["issues"]] == [0]
    assert [i["reason"].split(":")[0] for i in result["invalid"]] == ["sentence_out_of_range", "unknown_source"]


@pytest.mark.parametrize("issue_type", SEVEN)
def test_each_of_the_seven_types_is_accepted(claude, issue_type):
    evidence = "average revenue per account fell 4 percent" if issue_type == "changed_detail" else None

    result = _review(claude, _issue(type=issue_type, evidence=evidence))

    assert [i["type"] for i in result["issues"]] == [issue_type]


@pytest.mark.parametrize("fields", [
    {"type": "sounds_off"},
    {"type": "unsupported_by_citation"},                 # a type from before the seven
    {"type": "invented_reaction"},
    {"type": "claim_marked_as_view"},
    {"type": "invented_analogy"},
    {"excluded_by": "style"},                            # not one of the exclusions
    {"excluded_by": None},
])
def test_a_type_or_exclusion_outside_the_schema_is_not_a_usable_answer(claude, fields):
    from agents.review_agent import review_post

    bad = json.dumps({"issues": [_issue(**fields)]})
    claude.queue(bad, bad)

    result = review_post(_state())

    assert result["outcome"] == "not_reviewed" and result["error"].startswith("invalid_output")


def test_an_answer_without_the_reasoning_fields_is_not_a_usable_answer(claude):
    from agents.review_agent import review_post

    old_shape = json.dumps({"issues": [{"type": "not_in_sources", "sentence": 1, "sources": ["S1"],
                                        "evidence": None, "why": "The source does not say this."}]})
    claude.queue(old_shape, old_shape)

    assert review_post(_state())["outcome"] == "not_reviewed"


# --- Exclusions -------------------------------------------------------------------

@pytest.mark.parametrize("excluded_by", ["paraphrase", "opinion", "disclaimer", "authors_framing"])
def test_an_entry_the_model_excluded_is_recorded_and_never_counted(claude, excluded_by):
    result = _review(claude, _issue(excluded_by=excluded_by))

    assert result["outcome"] == "clean" and result["issues"] == [] and result["invalid"] == []
    [excluded] = result["excluded"]
    assert (excluded["excluded_by"], excluded["type"], excluded["sentence"]) == (excluded_by, "not_in_sources", 0)


def test_excluded_and_counted_entries_are_kept_apart(claude):
    result = _review(claude, _issue(sentence=1, excluded_by="paraphrase"), _issue(sentence=2, sources=[]),
                     _issue(sentence=3, sources=["S2"], excluded_by="disclaimer"), _issue(sentence=9))

    assert result["outcome"] == "issues"
    assert [i["sentence"] for i in result["issues"]] == [1]
    assert [(i["sentence"], i["excluded_by"]) for i in result["excluded"]] == [(0, "paraphrase"), (2, "disclaimer")]
    assert [i["sentence"] for i in result["invalid"]] == [8]


def test_an_excluded_entry_is_not_validated_it_is_only_recorded(claude):
    # Out of range, an unknown source and a made-up quote: none of it matters once the entry is excluded.
    result = _review(claude, _issue(sentence=40, sources=["S9"], evidence="not in any source", excluded_by="opinion"))

    assert result["invalid"] == [] and result["issues"] == []
    assert [(i["sentence"], i["span"], i["text"]) for i in result["excluded"]] == [(39, None, "")]


def test_code_decides_on_the_structured_fields_and_never_on_the_free_text(claude):
    # The words in analysis and why argue the other way in both entries: neither changes the outcome.
    counted = _issue(sentence=1, analysis="On reflection this is fine and does not count.",
                     why="Not a problem, a paraphrase.", excluded_by="none")
    excluded = _issue(sentence=2, sources=[], analysis="This is clearly an invented fact.",
                      why="A serious fabrication.", excluded_by="opinion")

    result = _review(claude, counted, excluded)

    assert [i["sentence"] for i in result["issues"]] == [0]
    assert [i["sentence"] for i in result["excluded"]] == [1]


# --- Not reviewed -----------------------------------------------------------------

def test_a_truncated_answer_is_not_reviewed_and_never_clean(claude):
    from agents.review_agent import review_post

    claude.queue(_cut_off(), _cut_off())                           # complete_structured asks twice

    result = review_post(_state())

    assert (result["outcome"], result["error"]) == ("not_reviewed", "truncated")
    assert result["issues"] == [] and result["invalid"] == []
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

    claude.queue(json.dumps({"issues": []}))
    with trace_calls() as outer:
        result = review_post(_state())

    assert [c["event_type"] for c in outer] == ["review"]
    assert (result["input_tokens"], result["output_tokens"]) == (outer[0]["input_tokens"], outer[0]["output_tokens"])
