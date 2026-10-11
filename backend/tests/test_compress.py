"""Compress (every single-writer variant): an over-length post is shortened by
one drafter-model call that returns shorter replacements for some sentences.
Code decides which may be used and splices them; no sentence is ever deleted,
merged or added, and a reply that cannot be used leaves the post as it was.
The model is the fake: whether a shorter sentence keeps its meaning is measured
on real calls, not here."""

import pytest
from anthropic.types import Message, RefusalStopDetails, TextBlock, Usage

from llm.models import OPUS_5_5, SONNET_4_6
from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import OWN, PROFILE, enveloped, make_state
from tests.length_fixtures import _cut_off, _outputs, _run
from tests.review_fixtures import fixes_reply
from tests.test_checks import SHORT_LINE, _post
from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)
from utils.formatters import count_words

# The shape of the production failure (trace fb714878): an argument the author
# sets up ("The opposing case sounds reasonable."), states, and rejects ("I
# don't buy it."). Sentences 2 to 4 share a line; 6 and 7 share one marker.
HOOK = "Most teams I talk to want to rebuild their ranker every single year."
SETUP = "The opposing case sounds reasonable."
OPPOSING = "A rebuild costs a whole quarter, and the old system still works well enough for most of the queries that matter."
REJECTION = "I don't buy it."
FACT = "We rebuilt the ranker in March and latency fell."
RESULT = "That is the kind of result a patch on the old system was never going to give us."
AFTER = "It also changed how the team works."
MARKED = (f"{HOOK} [[V]]\n\n{SETUP} [[V]] {OPPOSING} [[V]] {REJECTION} [[V]]\n\n{FACT} [[S1]]\n\n"
          f"{RESULT} {AFTER} [[V]]")
SENTENCES = [HOOK, SETUP, OPPOSING, REJECTION, FACT, RESULT, AFTER]
CLEAN = f"{HOOK}\n\n{SETUP} {OPPOSING} {REJECTION}\n\n{FACT}\n\n{RESULT} {AFTER}"
WORDS = count_words(CLEAN)

SHORT_HOOK = "Most teams I talk to want to rebuild their ranker yearly."                               # 2 words fewer
SHORT_OPPOSING = "A rebuild costs a quarter, and the old system still handles most queries that matter."   # 6 fewer
SHORT_RESULT = "No patch on the old system was going to give us that."                                 # 6 fewer


def _state(over_by: int = 8, marked: str = MARKED, **overrides):
    """The post finalised and checked, over its maximum by over_by words."""
    from pipeline.checks import checks_node
    from pipeline.finalise import finalise_draft_node
    from utils.citations import prose_word_count, strip_citations
    from utils.frames import build_sources_block

    words = prose_word_count(strip_citations(marked).text)
    state = make_state([OWN], archetype="general", current_draft=marked,
                       source_index=build_sources_block([OWN], PROFILE).index,
                       length_target={"min_words": 0, "max_words": words - over_by, "may_expand": False,
                                      "basis": "length_setting"}, **overrides)
    state = checks_node(finalise_draft_node(state))
    assert state["final_validation"]["over_by"] == over_by
    return state


def _compress(claude, state, reply):
    """The graph's steps from compress on: compress → finalise → checks again."""
    from agents.compress_agent import compress_node
    from pipeline.checks import recheck_node
    from pipeline.finalise import refinalise_node

    claude.queue(reply)
    return recheck_node(refinalise_node(compress_node(state)))


def _spans_match(state) -> bool:
    return all(state["final_post"][c["start"]:c["end"]] == c["text"] for c in state["citations"])


# --- The call ----------------------------------------------------------------------

def test_an_over_length_post_makes_exactly_one_call_that_shows_sources_sentences_and_the_excess(claude):
    from utils.frames import SOURCES_ARE_DATA_RULE

    state = _compress(claude, _state(), fixes_reply({1: f"{SHORT_HOOK} [[V]]", 3: f"{SHORT_OPPOSING} [[V]]"}))

    [call] = claude.calls                                         # one call, and no second one
    assert call["model"] == SONNET_4_6 and "tools" not in call
    prompt = call["messages"][-1]["content"]
    assert f'<sources>\n<source id="S1"' in prompt and OWN["text"] in prompt and SOURCES_ARE_DATA_RULE in call["system"]
    numbered = prompt[prompt.index("<post_sentences>") + 17:prompt.index("</post_sentences>")].strip().splitlines()
    assert numbered == [f'{n}. ({count_words(text)} words) "{text}" {"[[S1]]" if text == FACT else "[[V]]"}'
                        for n, text in enumerate(SENTENCES, 1)]
    assert f"The post is {WORDS} words long. Its limit is {WORDS - 8} words, so at least 8 words have to go." in prompt
    assert state["compress_result"]["outcome"] == "compressed"


def test_a_post_that_is_not_over_its_maximum_is_never_sent_to_compress():
    from pipeline.finalise import route_to_compress

    assert route_to_compress({"final_validation": {"length": "over_length"}}) == "compress"
    for length in ("ok", "under_length", "no_target"):
        assert route_to_compress({"final_validation": {"length": length}}) == "end"


# --- Accepted replacements ------------------------------------------------------------

def test_accepted_replacements_are_spliced_and_every_other_sentence_is_byte_identical(claude):
    state = _state()
    spans_before = state["citations"]

    state = _compress(claude, state, fixes_reply({1: f"{SHORT_HOOK} [[V]]", 3: f"{SHORT_OPPOSING} [[V]]",
                                                  6: f"{SHORT_RESULT} [[V]]"}))

    # Exactly the three sentences changed: putting them into the old text gives the new text.
    expected = CLEAN.replace(HOOK, SHORT_HOOK).replace(OPPOSING, SHORT_OPPOSING).replace(RESULT, SHORT_RESULT)
    assert state["final_post"] == state["current_draft"] == expected
    for kept in (SETUP, REJECTION, FACT, AFTER):
        assert kept in state["final_post"]
    result = state["compress_result"]
    assert result["outcome"] == "compressed" and result["rejected"] == []
    assert (result["words_before"], result["words_after"]) == (WORDS, WORDS - 14)
    assert result["accepted"] == [
        {"sentence": 1, "before": f"{HOOK} [[V]]", "after": f"{SHORT_HOOK} [[V]]", "words_before": 13, "words_after": 11},
        {"sentence": 3, "before": f"{OPPOSING} [[V]]", "after": f"{SHORT_OPPOSING} [[V]]", "words_before": 21, "words_after": 15},
        {"sentence": 6, "before": f"{RESULT} [[V]]", "after": f"{SHORT_RESULT} [[V]]", "words_before": 18, "words_after": 12},
    ]
    # The spans are the same spans over the new text: same count, same citations, offsets that fit.
    assert [(c["basis"], c["sources"]) for c in state["citations"]] == [(c["basis"], c["sources"]) for c in spans_before]
    assert _spans_match(state) and state["citations"][-1]["text"] == f"{SHORT_RESULT} {AFTER}"
    assert "spans_stale" not in state["final_validation"]
    assert state["draft_history"][-1] == {"node": "compress", "iteration": 0, "text": expected}


def test_the_framing_of_an_opposing_view_survives_a_reply_that_tries_to_delete_it(claude):
    # What the trim did in production: drop the set-up and the rejection, the cheapest words to lose.
    reply = fixes_reply({3: f"{SHORT_OPPOSING} [[V]]", 6: f"{SHORT_RESULT} [[V]]"}, delete=(2, 4))

    state = _compress(claude, _state(), reply)

    assert f"{SETUP} {SHORT_OPPOSING} {REJECTION}" in state["final_post"]
    result = state["compress_result"]
    assert result["outcome"] == "compressed" and [entry["sentence"] for entry in result["accepted"]] == [3, 6]
    assert result["rejected"] == [{"sentence": 2, "reason": "deletion", "text": ""},
                                  {"sentence": 4, "reason": "deletion", "text": ""}]


def test_a_replacement_is_normalised_before_it_is_measured_and_spliced(claude):
    # "ranker—yearly." is one word until the em dash is normalised: the replacement is then eleven words, not ten.
    state = _compress(claude, _state(over_by=1), fixes_reply({1: "Most teams I talk to want to rebuild their ranker—yearly. [[V]]"}))

    [accepted] = state["compress_result"]["accepted"]
    assert (accepted["after"], accepted["words_after"]) == ("Most teams I talk to want to rebuild their ranker, yearly. [[V]]", 11)
    assert "—" not in state["final_post"] and "spans_stale" not in state["final_validation"] and _spans_match(state)


# --- Rejected replacements --------------------------------------------------------------

@pytest.mark.parametrize("fix,reason", [
    (f'<fix sentence="3">{OPPOSING} And then some more of it. [[V]]</fix>', "not_one_sentence"),
    (f'<fix sentence="3">{OPPOSING.replace("whole quarter", "whole long quarter")} [[V]]</fix>', "not_shorter"),
    (f'<fix sentence="3">{OPPOSING} [[V]]</fix>', "not_shorter"),                        # the sentence as it was
    ('<fix sentence="3"></fix>', "empty"),
    ('<fix sentence="3">[[V]]</fix>', "empty"),
    ('<fix sentence="3" delete="true"/>', "deletion"),
    (f'<fix sentence="3">{SHORT_OPPOSING} [[S1]]</fix>', "marker_wrong"),
    (f'<fix sentence="5">We rebuilt the ranker in March. [[V]]</fix>', "marker_wrong"),
    (f'<fix sentence="3">{SHORT_OPPOSING}</fix>', "marker_missing"),
    (f'<fix sentence="3">{SHORT_OPPOSING} [[S1 and V]]</fix>', "marker_failure: ['malformed']"),
    ('<fix sentence="3">A rebuild costs 3 months, and the old system still handles most queries. [[V]]</fix>',
     "new_specific: ['3 months']"),
    ('<fix sentence="5">We rebuilt the ranker last March. [[S1]]</fix>', "new_specific: ['last March']"),
    (f'<fix sentence="99">{SHORT_OPPOSING} [[V]]</fix>', "unknown_sentence"),
    (f'<fix sentence="0">{SHORT_OPPOSING} [[V]]</fix>', "unknown_sentence"),
    (f'<fix sentence="3">{SHORT_OPPOSING} [[V]]</fix><fix sentence="3">A rebuild costs a quarter. [[V]]</fix>', "repeated"),
    # A merge: sentence 3 rewritten to carry sentence 4 as well, as two sentences or as two cited pieces.
    ('<fix sentence="3">A rebuild costs a quarter. I disagree. [[V]]</fix>', "not_one_sentence"),
    ('<fix sentence="3">A rebuild costs a quarter. [[V]] I disagree. [[V]]</fix>', "not_one_sentence"),
])
def test_a_rejected_replacement_keeps_its_sentence_and_records_why(claude, fix, reason):
    state = _state()

    state = _compress(claude, state, f"<fixes>\n{fix}\n</fixes>")

    result = state["compress_result"]
    assert [entry["reason"] for entry in result["rejected"]] == [reason]
    assert result["accepted"] == [] and state["final_post"] == CLEAN       # nothing changed
    assert (result["outcome"], result["words_after"]) == ("still_over", WORDS)
    assert [d["node"] for d in state["draft_history"]] == []               # no compress entry: the post is the draft
    assert len(claude.calls) == 1


def test_a_replacement_that_keeps_its_sentences_own_specific_is_accepted(claude):
    state = _compress(claude, _state(over_by=1), fixes_reply({5: "We rebuilt the ranker in March; latency fell. [[S1]]"}))

    assert [entry["sentence"] for entry in state["compress_result"]["accepted"]] == [5]


def test_valid_replacements_are_used_when_others_in_the_same_reply_are_rejected(claude):
    reply = fixes_reply({1: f"{SHORT_HOOK} [[V]]", 3: f"{SHORT_OPPOSING} [[S1]]", 6: f"{SHORT_RESULT} [[V]]"})

    state = _compress(claude, _state(), reply)

    result = state["compress_result"]
    assert [entry["sentence"] for entry in result["accepted"]] == [1, 6]
    assert result["rejected"] == [{"sentence": 3, "reason": "marker_wrong", "text": f"{SHORT_OPPOSING} [[S1]]"}]
    assert state["final_post"] == CLEAN.replace(HOOK, SHORT_HOOK).replace(RESULT, SHORT_RESULT)
    assert (result["outcome"], result["words_after"]) == ("compressed", WORDS - 8)


# --- List markers -----------------------------------------------------------------------

BULLETS = ("Three things changed for us. [[V]]\n\n"
           "- We rebuilt the ranker in March and latency fell quite a lot. [[S1]]\n"
           "* The team stopped arguing about the old system every single week. [[V]]\n"
           "2. Nobody on the team wants the old system back now. [[V]]")


@pytest.mark.parametrize("fix,reason", [
    ('<fix sentence="2">We rebuilt the ranker in March; latency fell. [[S1]]</fix>', "list_marker_lost"),
    ('<fix sentence="2">* We rebuilt the ranker in March; latency fell. [[S1]]</fix>', "list_marker_lost"),
    ('<fix sentence="3">The team stopped arguing about the old system. [[V]]</fix>', "list_marker_lost"),
    ('<fix sentence="4">Nobody wants the old system back. [[V]]</fix>', "list_marker_lost"),
    ('<fix sentence="4">3. Nobody wants the old system back. [[V]]</fix>', "list_marker_lost"),
])
def test_a_replacement_that_loses_or_changes_its_sentences_list_marker_is_rejected(claude, fix, reason):
    state = _state(over_by=3, marked=BULLETS)
    before = state["final_post"]

    state = _compress(claude, state, f"<fixes>\n{fix}\n</fixes>")

    assert [entry["reason"] for entry in state["compress_result"]["rejected"]] == [reason]
    assert state["compress_result"]["accepted"] == [] and state["final_post"] == before


def test_a_replacement_that_keeps_its_list_marker_is_spliced_onto_its_line(claude):
    state = _state(over_by=3, marked=BULLETS)

    state = _compress(claude, state, fixes_reply({2: "- We rebuilt the ranker in March; latency fell. [[S1]]",
                                                  4: "2. Nobody wants the old system back. [[V]]"}))

    result = state["compress_result"]
    assert result["outcome"] == "compressed" and result["rejected"] == []
    assert state["final_post"] == ("Three things changed for us.\n\n"
                                   "- We rebuilt the ranker in March; latency fell.\n"
                                   "* The team stopped arguing about the old system every single week.\n"
                                   "2. Nobody wants the old system back.")


# --- Still over ---------------------------------------------------------------------------

def test_accepted_replacements_that_do_not_reach_the_limit_are_kept_and_recorded_as_still_over(claude):
    state = _compress(claude, _state(), fixes_reply({1: f"{SHORT_HOOK} [[V]]"}))       # 2 of the 8 words

    result = state["compress_result"]
    assert (result["outcome"], result["reason"]) == ("still_over", None)
    assert (result["words_before"], result["words_after"]) == (WORDS, WORDS - 2)
    assert state["final_post"] == CLEAN.replace(HOOK, SHORT_HOOK)                       # the shorter post is kept
    assert (state["final_validation"]["length"], state["final_validation"]["over_by"]) == ("over_length", 6)
    assert state["checks_final"]["counts"] == {"over_length": 1}
    assert len(claude.calls) == 1                                                     # never a second call


# --- Replies that cannot be used ----------------------------------------------------------

def _refused() -> Message:
    return Message(id="msg_refused", type="message", role="assistant", model="fake", content=[],
                   stop_reason="refusal", stop_sequence=None,
                   stop_details=RefusalStopDetails(type="refusal", category=None, explanation=None),
                   usage=Usage(input_tokens=10, output_tokens=0))


def _empty() -> Message:
    return Message(id="msg_empty", type="message", role="assistant", model="fake",
                   content=[TextBlock(type="text", text="  \n")], stop_reason="end_turn", stop_sequence=None,
                   usage=Usage(input_tokens=10, output_tokens=1))


@pytest.mark.parametrize("reply,reason,stop_reason", [
    (_refused(), "refused", "refusal"),
    (_cut_off(f'<fixes>\n<fix sentence="1">{SHORT_HOOK} [[V]]</fix>\n<fix sentence="3">A rebuild'), "truncated", "max_tokens"),
    (_empty(), "empty_output", "end_turn"),
    (f"{SHORT_HOOK} [[V]]\n\n{SETUP} [[V]]", "malformed_output: fixes_tag_missing", "end_turn"),   # a rewritten post
    ("<fixes>\n</fixes>", "no_replacements", "end_turn"),
    ("<fixes>\nNothing here can be shortened.\n</fixes>", "no_replacements", "end_turn"),
])
def test_a_reply_that_cannot_be_used_keeps_the_unshortened_post_with_its_reason(claude, reply, reason, stop_reason):
    state = _state()

    state = _compress(claude, state, reply)

    result = state["compress_result"]
    assert (result["outcome"], result["reason"], result["stop_reason"]) == ("compress_failed", reason, stop_reason)
    assert result["accepted"] == [] and result["rejected"] == []
    assert (result["words_before"], result["words_after"]) == (WORDS, WORDS)
    assert state["final_post"] == state["current_draft"] == CLEAN             # a cut-off reply is not read at all
    assert state["final_validation"]["length"] == "over_length"
    assert len(claude.calls) == 1                                             # never a second call


def test_an_api_error_during_compress_is_a_recorded_failure(claude):
    import anthropic
    import httpx

    from agents.compress_agent import compress_node

    def overloaded(kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    claude.respond_with(overloaded)
    state = compress_node(_state())

    result = state["compress_result"]
    assert (result["outcome"], result["reason"], result["stop_reason"]) == (
        "compress_failed", "api_error: InternalServerError", None)
    assert state["current_draft"] == CLEAN and len(claude.calls) == 1


# --- Through run_pipeline -------------------------------------------------------------------

@pytest.mark.parametrize("variant,model", [("C", SONNET_4_6), ("C-Opus", OPUS_5_5)])
def test_the_run_records_the_result_checks_it_and_logs_usage_with_the_model_id(claude, fake_db, seeded_kb, monkeypatch,
                                                                              variant, model):
    import llm.client as llm_client

    usage: list[dict] = []
    monkeypatch.setattr(llm_client, "schedule_usage_event", lambda **kw: usage.append(kw))
    claude.queue(ARCHETYPE_GENERAL, enveloped(_post(36)),
                 fixes_reply({n: SHORT_LINE for n in (10, 11, 12, 13)}))                 # 360 words against 250-350

    result = _run(variant)

    outputs = _outputs(fake_db)
    compress = outputs["compress_result"]
    assert (compress["outcome"], compress["model"], compress["stop_reason"]) == ("compressed", model, "end_turn")
    assert (compress["words_before"], compress["words_after"]) == (360, 348)
    # The usage row and the trace's call both carry the exact model id.
    [row] = [u for u in usage if u["event_type"] == "compress"]
    assert row["model"] == model and row["user_id"]
    [trace] = fake_db.tables["generation_traces"]
    assert [(c["event_type"], c["model"]) for c in trace["llm_calls"]][-1] == ("compress", model)
    # The checks ran on the compressed post, and the returned post is the last validated text.
    assert outputs["checks_before_trim"]["counts"] == {"over_length": 1}
    assert outputs["checks_final"] == {"issues": [], "counts": {}}
    assert result["post"] == outputs["final_post"] == outputs["draft_history"][-1]["text"]
    assert outputs["final_validation"]["words"] == count_words(result["post"]) == 348
    assert outputs["final_validation"]["length"] == "ok" and "trim_result" not in outputs
    assert len(claude.calls) == 3                                           # structure, draft, compress
