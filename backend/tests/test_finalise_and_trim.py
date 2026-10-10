"""Final validation, trim by deletion and truncated drafts.

finalise() is the last thing that touches a post in every variant; the returned
post is always the string it validated. Variants B and C trim an over-length
post by deleting whole spans, never lengthen one, and return no post when the
draft was cut off. Pipeline A is recorded only."""

import json

import pytest
from anthropic.types import Message, TextBlock, Usage

from tests.conftest import ARCHETYPE_GENERAL, CRITIC_ALL_STRONG
from tests.generation_fixtures import OWN, make_state
from tests.test_generation_trace import STANDARD_RUN, USER as KB_USER, seeded_kb  # noqa: F401  (shared fixture)
from utils.formatters import FIRST_POST_RANGE, WORD_RANGES, count_words, resolve_length_target

FIRST_POST_USER = "user-first-post"   # no posts and no notes: every run is a first post (70-100 words)
TRIM = "claude-haiku-4-5-20251001"


def _lines(count: int, words_each: int = 10, marker: str = "[[V]]") -> list[str]:
    """count one-span lines of words_each words, each with a marker."""
    filler = " ".join(["word"] * (words_each - 2))
    return [f"Line {i} {filler} {marker}" for i in range(1, count + 1)]


def _post(count: int, words_each: int = 10) -> str:
    return "\n\n".join(_lines(count, words_each))


def _clean(marked: str) -> str:
    from utils.citations import strip_citations

    return strip_citations(marked).text


def _cut_off(text: str = "") -> Message:
    return Message(id="msg_cut", type="message", role="assistant", model="fake",
                   content=[TextBlock(type="text", text=text)], stop_reason="max_tokens",
                   stop_sequence=None, usage=Usage(input_tokens=10, output_tokens=2000))


def _run(variant, user_id=KB_USER, **overrides):
    from pipeline.graph import run_pipeline

    kwargs = dict(topic="pgvector retrieval", format="linkedin post", tone="casual", user_id=user_id, variant=variant)
    kwargs.update(overrides)
    return run_pipeline(**kwargs)


def _outputs(fake_db) -> dict:
    [trace] = fake_db.tables["generation_traces"]
    return trace["node_outputs"]


# --- finalise: one function, the record is of the string it returns ------------------

def test_finalise_normalises_then_measures_the_normalised_text():
    from pipeline.finalise import finalise

    target = resolve_length_target("linkedin post", "standard", first_post=True)
    text = " ".join(["word"] * 99) + " alpha—beta"
    assert count_words(text) == 100

    finalised = finalise(text, target)

    assert finalised.text.endswith("alpha, beta")
    assert finalised.record == {
        "words": 101, "target": {"min_words": 70, "max_words": 100, "basis": "first_post"},
        "length": "over_length", "over_by": 1, "under_by": 0,
        "leftover_markers": [], "em_dashes_remaining": 0,
    }
    assert finalised.record["words"] == count_words(finalised.text)


@pytest.mark.parametrize("words,length,over_by,under_by", [
    (250, "ok", 0, 0), (350, "ok", 0, 0), (351, "over_length", 1, 0), (249, "under_length", 0, 1), (3, "under_length", 0, 247),
])
def test_the_record_says_how_far_over_or_under(words, length, over_by, under_by):
    from pipeline.finalise import finalise

    record = finalise(" ".join(["word"] * words), resolve_length_target("linkedin post", "standard")).record

    assert (record["words"], record["length"], record["over_by"], record["under_by"]) == (words, length, over_by, under_by)


def test_a_thin_sources_target_has_no_floor_and_a_thread_has_no_target():
    from pipeline.finalise import finalise

    thin = finalise("Three words only.", resolve_length_target("linkedin post", "standard", thin_sources=True)).record
    thread = finalise("1/ A tweet.", resolve_length_target("thread", "standard")).record

    assert (thin["length"], thin["under_by"]) == ("ok", 0)
    assert (thread["length"], thread["target"], thread["words"]) == ("no_target", None, 3)


def test_leftover_markers_and_protected_em_dashes_are_recorded_not_removed():
    from pipeline.finalise import finalise

    text = "A stray marker. [S2]\n\n```\ncode — untouched [[S1]]\n```\n\nAnother [[V]] here."

    finalised = finalise(text, None)

    assert finalised.text == text
    assert [(m["kind"], m["text"]) for m in finalised.record["leftover_markers"]] == [
        ("single_brackets", "[S2]"), ("leftover", "[[V]]")]
    assert finalised.record["em_dashes_remaining"] == 0   # the one em dash is inside code


def test_finalise_is_idempotent():
    from pipeline.finalise import finalise

    once = finalise("Fast—really fast. It held — mostly. Pages 3—5.", None)

    assert finalise(once.text, None) == once


def test_finalise_marked_gives_spans_that_index_the_returned_text():
    from pipeline.finalise import finalise_marked

    finalised, stripped = finalise_marked("It was fast — really fast. [[S1]] Then it held—mostly. [[V]]", None)

    assert finalised.text == "It was fast, really fast. Then it held, mostly."
    assert [finalised.text[s.start:s.end] for s in stripped.spans] == ["It was fast, really fast.", "Then it held, mostly."]
    assert finalised.record["words"] == count_words(finalised.text)
    assert finalised.record["em_dashes_remaining"] == 0


# --- Deleting spans -----------------------------------------------------------------

MARKED = ("Hook. [[V]]\n\nA one. [[S1]] A two. [[S1]] A three. [[V]]\n\nOnly line. [[S1]]\n\n"
          "## Heading\n  Indented a. [[S1]] Indented b. [[V]]\n\nLast. [[V]]")


@pytest.mark.parametrize("delete,expected", [
    ({2}, "Hook.\n\nA one. A three.\n\nOnly line.\n\n## Heading\n  Indented a. Indented b.\n\nLast."),
    ({1, 2, 3}, "Hook.\n\nOnly line.\n\n## Heading\n  Indented a. Indented b.\n\nLast."),
    ({4}, "Hook.\n\nA one. A two. A three.\n\n## Heading\n  Indented a. Indented b.\n\nLast."),
    ({0}, "A one. A two. A three.\n\nOnly line.\n\n## Heading\n  Indented a. Indented b.\n\nLast."),
    ({7}, "Hook.\n\nA one. A two. A three.\n\nOnly line.\n\n## Heading\n  Indented a. Indented b."),
    ({5, 6}, "Hook.\n\nA one. A two. A three.\n\nOnly line.\n\n## Heading\n\nLast."),
    (set(), "Hook.\n\nA one. A two. A three.\n\nOnly line.\n\n## Heading\n  Indented a. Indented b.\n\nLast."),
])
def test_deleting_spans_removes_exactly_those_spans_and_closes_the_gaps(delete, expected):
    from utils.citations import delete_spans, strip_citations

    stripped = strip_citations(MARKED)

    text, kept = delete_spans(stripped.text, stripped.spans, delete)

    assert text == expected
    assert [s.text for s in kept] == [s.text for i, s in enumerate(stripped.spans) if i not in delete]
    assert [(s.basis, s.sources) for s in kept] == [(s.basis, s.sources) for i, s in enumerate(stripped.spans) if i not in delete]
    for span in kept:
        assert text[span.start:span.end] == span.text
    assert count_words(text) == count_words(stripped.text) - sum(count_words(stripped.spans[i].text) for i in delete)


def test_deleting_spans_never_touches_code_or_adds_a_word():
    from utils.citations import delete_spans, strip_citations

    stripped = strip_citations("Intro line. [[V]]\n\n```python\nprint('kept')\n```\n\nDrop me. [[S1]]\n\nOutro. [[V]]")

    text, _ = delete_spans(stripped.text, stripped.spans, {1})

    assert text == "Intro line.\n\n```python\nprint('kept')\n```\n\nOutro."
    assert set(text.split()) <= set(stripped.text.split())


# --- The trim node ---------------------------------------------------------------

def _trim_state(count=12, words_each=10, max_words=100):
    from pipeline.finalise import finalise_draft_node

    state = make_state([OWN], archetype="general", current_draft=_post(count, words_each),
                       length_target={"min_words": 70, "max_words": max_words, "may_expand": False, "basis": "first_post"})
    return finalise_draft_node(state)


def _trim(claude, state, *replies):
    from agents.word_count_enforcer_agent import trim_node
    from pipeline.finalise import finalise_trimmed_node

    claude.queue(*replies)
    return finalise_trimmed_node(trim_node(state))


def test_trim_deletes_the_chosen_spans_and_the_post_is_measured_again(claude):
    state = _trim_state()                       # 12 spans of 10 words: 120 against a maximum of 100
    before = state["final_post"]

    state = _trim(claude, state, json.dumps({"delete": [3, 7]}))

    [call] = claude.calls
    assert call["model"] == TRIM and call["tool_choice"]["name"] == "choose_spans_to_delete"
    assert state["trim_result"] == {
        "outcome": "trimmed", "reason": None, "max_words": 100, "words_before": 120, "words_after": 100,
        "deleted": [{"index": 2, "text": _clean(_lines(12)[2])}, {"index": 6, "text": _clean(_lines(12)[6])}],
    }
    assert state["final_post"] == "\n\n".join(_clean(l) for i, l in enumerate(_lines(12)) if i not in (2, 6))
    assert state["final_validation"]["words"] == count_words(state["final_post"]) == 100
    assert state["final_validation"]["length"] == "ok"
    assert len(state["citations"]) == 10
    for c in state["citations"]:
        assert state["final_post"][c["start"]:c["end"]] == c["text"]
    assert set(state["final_post"].split()) <= set(before.split())   # nothing written, only removed


def test_the_trim_call_sees_numbered_spans_their_lengths_and_the_maximum(claude):
    state = _trim_state()
    _trim(claude, state, json.dumps({"delete": [2, 3]}))

    prompt = claude.calls[0]["messages"][-1]["content"]
    for number, line in enumerate(_lines(12), 1):
        assert f"{number}. (10 words) {_clean(line)}" in prompt
    assert "120" in prompt and "100" in prompt and "20" in prompt   # length, maximum, excess


def test_a_trim_that_leaves_the_post_over_is_a_recorded_failure(claude):
    state = _trim(claude, _trim_state(), json.dumps({"delete": [5]}))

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"] == "still_over"
    assert (state["trim_result"]["words_before"], state["trim_result"]["words_after"]) == (120, 110)
    assert [d["index"] for d in state["trim_result"]["deleted"]] == [4]
    assert state["final_validation"]["length"] == "over_length" and state["final_validation"]["over_by"] == 10
    assert state["final_validation"]["words"] == count_words(state["final_post"]) == 110
    assert len(claude.calls) == 1                                   # one bounded attempt, no second call


@pytest.mark.parametrize("delete,reason", [
    ([0], "invalid_indices"), ([13], "invalid_indices"), ([2, 99], "invalid_indices"), ([-1], "invalid_indices"),
    ([], "no_spans_chosen"), (list(range(1, 13)), "all_spans_chosen"),
])
def test_unusable_span_numbers_are_rejected_and_the_post_is_left_untrimmed(claude, delete, reason):
    state = _trim_state()
    before = state["final_post"]

    state = _trim(claude, state, json.dumps({"delete": delete}))

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"].startswith(reason)
    assert state["trim_result"]["deleted"] == [] and state["trim_result"]["words_after"] == 120
    assert state["final_post"] == before
    assert state["final_validation"]["length"] == "over_length"


def test_repeated_span_numbers_delete_the_span_once(claude):
    state = _trim(claude, _trim_state(), json.dumps({"delete": [3, 3, 7, 7]}))

    assert state["trim_result"]["outcome"] == "trimmed"
    assert [d["index"] for d in state["trim_result"]["deleted"]] == [2, 6]


def test_a_truncated_trim_answer_is_a_recorded_failure_and_nothing_is_deleted(claude):
    state = _trim_state()
    before = state["final_post"]

    state = _trim(claude, state, _cut_off(), _cut_off())      # complete_structured asks twice

    assert state["trim_result"]["outcome"] == "trim_failed" and state["trim_result"]["reason"] == "truncated"
    assert state["trim_result"]["deleted"] == []
    assert state["final_post"] == before
    assert state["final_validation"]["length"] == "over_length"


def test_a_trim_answer_that_is_not_a_tool_call_is_a_recorded_failure(claude):
    state = _trim_state()
    before = state["final_post"]

    state = _trim(claude, state, "Delete spans 3 and 7.", "Delete spans 3 and 7.")

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"].startswith("invalid_output")
    assert state["final_post"] == before


def test_an_api_error_during_the_trim_is_a_recorded_failure(claude):
    import anthropic
    import httpx

    def overloaded(kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    state = _trim_state()
    before = state["final_post"]
    claude.respond_with(overloaded)

    from agents.word_count_enforcer_agent import trim_node
    state = trim_node(state)

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"] == "api_error: InternalServerError"
    assert state["current_draft"] == before


# --- Through run_pipeline, variants B and C --------------------------------------

@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_first_post_made_over_length_by_normalisation_is_trimmed(claude, fake_db, variant):
    # Ten 10-word lines: 100 words, the first-post maximum. One holds "alpha—beta",
    # which is one word until the em dash is normalised: then the post is 101.
    lines = _lines(10)
    lines[4] = lines[4].replace("word", "alpha—beta", 1)
    marked = "\n\n".join(lines)
    assert count_words(_clean(marked)) == FIRST_POST_RANGE[1]      # 100 before normalisation
    claude.queue(ARCHETYPE_GENERAL, marked, json.dumps({"delete": [2]}))

    result = _run(variant, user_id=FIRST_POST_USER, topic="Forecast intervals",
                  context="Core opinion/take: intervals beat point forecasts")

    outputs = _outputs(fake_db)
    assert outputs["length_target"]["basis"] == "first_post"
    assert outputs["trim_result"]["words_before"] == FIRST_POST_RANGE[1] + 1      # validated after normalisation
    assert outputs["trim_result"]["outcome"] == "trimmed"
    assert "alpha, beta" in result["post"] and "—" not in result["post"]
    assert outputs["final_validation"]["words"] == count_words(result["post"]) <= FIRST_POST_RANGE[1]
    assert outputs["final_post"] == result["post"]
    assert [c["event_type"] for c in fake_db.tables["generation_traces"][0]["llm_calls"]] == ["archetype", "generate", "trim"]


@pytest.mark.parametrize("variant", ["B", "C"])
def test_an_over_length_post_is_trimmed_and_the_returned_post_is_the_validated_one(claude, fake_db, seeded_kb, variant):
    claude.queue(ARCHETYPE_GENERAL, _post(36), json.dumps({"delete": [10]}))   # 360 words against 250-350

    result = _run(variant)

    outputs = _outputs(fake_db)
    assert outputs["trim_result"]["outcome"] == "trimmed"
    assert (outputs["trim_result"]["words_before"], outputs["trim_result"]["words_after"]) == (360, 350)
    assert outputs["trim_result"]["deleted"] == [{"index": 9, "text": _clean(_lines(36)[9])}]
    assert result["status"] == "ok"
    assert result["post"] == outputs["final_post"]
    assert outputs["final_validation"]["words"] == count_words(result["post"]) == 350
    assert [d["node"] for d in outputs["draft_history"]] == ["draft", "trim"]
    assert len(outputs["citations"]) == 35


@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_failed_trim_returns_the_post_with_the_failure_recorded(claude, fake_db, seeded_kb, variant):
    claude.queue(ARCHETYPE_GENERAL, _post(36), json.dumps({"delete": [99]}))

    result = _run(variant)

    outputs = _outputs(fake_db)
    assert outputs["trim_result"]["outcome"] == "trim_failed"
    assert outputs["trim_result"]["reason"].startswith("invalid_indices")
    assert result["status"] == "ok" and count_words(result["post"]) == 360
    assert outputs["final_validation"]["length"] == "over_length" and outputs["final_validation"]["over_by"] == 10
    assert result["post"] == outputs["final_post"]


@pytest.mark.parametrize("variant", ["B", "C"])
def test_an_under_length_post_is_recorded_and_costs_no_extra_call(claude, fake_db, seeded_kb, variant):
    claude.queue(ARCHETYPE_GENERAL, _post(5))          # 50 words against 250-350

    result = _run(variant)

    outputs = _outputs(fake_db)
    assert len(claude.calls) == 2                      # structure and draft: nothing lengthens a post
    assert outputs["final_validation"]["length"] == "under_length"
    assert (outputs["final_validation"]["words"], outputs["final_validation"]["under_by"]) == (50, 200)
    assert "trim_result" not in outputs
    assert result["post"] == outputs["final_post"] and count_words(result["post"]) == 50


@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_post_within_its_target_is_not_trimmed(claude, fake_db, seeded_kb, variant):
    claude.queue(ARCHETYPE_GENERAL, _post(30))         # 300 words

    _run(variant)

    assert len(claude.calls) == 2
    assert _outputs(fake_db)["final_validation"]["length"] == "ok"
    assert "trim_result" not in _outputs(fake_db)


# --- Truncated drafts ------------------------------------------------------------

@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_cut_off_draft_returns_an_error_status_and_no_post(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import DRAFT_TRUNCATED_MESSAGE

    cut = "pgvector makes retrieval fast. [[S1]]\n\nAnd the reason it matters is that"
    claude.queue(ARCHETYPE_GENERAL, _cut_off(cut))

    result = _run(variant)

    assert result["status"] == "draft_truncated"
    assert result["post"] == ""
    assert result["message"] == DRAFT_TRUNCATED_MESSAGE
    assert len(claude.calls) == 2                      # no trim, no second draft
    outputs = _outputs(fake_db)
    assert outputs["draft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert outputs["final_post"] == ""
    assert outputs["draft_history"] == [{"node": "draft", "iteration": 0, "text": cut}]   # kept for diagnosis only
    assert "final_validation" not in outputs


def test_the_generate_endpoint_reports_a_cut_off_draft(claude, fake_db, seeded_kb, client, auth_headers, monkeypatch):
    from pipeline.graph import DRAFT_TRUNCATED_MESSAGE

    monkeypatch.setenv("PIPELINE_VARIANT", "C")
    claude.queue(ARCHETYPE_GENERAL, _cut_off("pgvector makes retrieval"))

    resp = client.post("/generate", json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"},
                       headers=auth_headers(KB_USER))

    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["post"], body["message"]) == ("draft_truncated", "", DRAFT_TRUNCATED_MESSAGE)


def test_an_ordinary_response_has_an_empty_message(claude, fake_db, seeded_kb, client, auth_headers):
    claude.queue(*STANDARD_RUN)

    resp = client.post("/generate", json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"},
                       headers=auth_headers(KB_USER))

    assert resp.json()["status"] == "ok" and resp.json()["message"] == ""


# --- The draft's output budget ---------------------------------------------------

def _every_target():
    targets = [resolve_length_target(fmt, length) for fmt, lengths in WORD_RANGES.items() for length in lengths]
    targets += [resolve_length_target(fmt, length, thin_sources=True) for fmt, lengths in WORD_RANGES.items() for length in lengths]
    return targets + [resolve_length_target("linkedin post", "standard", first_post=True)]


def test_the_draft_budget_fits_every_length_target_with_markers():
    from utils.formatters import DRAFT_TOKEN_MARGIN, MIN_DRAFT_MAX_TOKENS, TOKENS_PER_WORD, draft_max_tokens

    assert max(t["max_words"] for t in _every_target()) == 1800      # Medium long-form is in the table
    for target in _every_target():
        budget = draft_max_tokens(target)
        assert budget >= target["max_words"] * TOKENS_PER_WORD * DRAFT_TOKEN_MARGIN, target
        assert budget >= MIN_DRAFT_MAX_TOKENS
    assert draft_max_tokens(resolve_length_target("thread", "long-form")) == MIN_DRAFT_MAX_TOKENS
    assert DRAFT_TOKEN_MARGIN > 1


def test_the_largest_draft_budget_is_within_the_non_streaming_ceiling():
    from llm.client import MAX_NON_STREAMING_OUTPUT_TOKENS
    from utils.formatters import draft_max_tokens

    assert max(draft_max_tokens(t) for t in _every_target()) <= MAX_NON_STREAMING_OUTPUT_TOKENS


@pytest.mark.parametrize("fmt,length,expected", [
    ("linkedin post", "standard", 2000), ("medium article", "standard", 2138), ("medium article", "long-form", 4275),
])
def test_the_draft_call_asks_for_the_budget_its_target_needs(claude, fmt, length, expected):
    from agents.draft_agent import cited_draft_node

    claude.queue("The post. [[V]]")
    cited_draft_node(make_state([OWN], archetype="general", format=fmt, length=length,
                                length_target=resolve_length_target(fmt, length)))

    assert claude.calls[0]["max_tokens"] == expected


# --- Pipeline A: recorded only ----------------------------------------------------

def test_pipeline_a_returns_the_same_post_and_stores_the_validation_record(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    result = _run("A")

    record = _outputs(fake_db)["final_validation"]
    assert result["post"] == "Final text."               # what STANDARD_RUN has always produced
    assert record["words"] == count_words(result["post"]) == 2
    assert (record["length"], record["under_by"]) == ("under_length", 248)
    assert record["target"] == {"min_words": 250, "max_words": 350, "basis": "length_setting"}
    assert "trim_result" not in _outputs(fake_db)


def test_pipeline_a_first_post_made_101_words_by_normalisation_is_recorded_and_returned_unchanged(claude, fake_db):
    from utils.formatters import normalise_post_punctuation

    draft = " ".join(["word"] * 99) + " alpha—beta"     # 100 words to the enforcer, 101 once normalised
    claude.queue(ARCHETYPE_GENERAL, draft, CRITIC_ALL_STRONG, draft, "CLEAN", draft)

    result = _run("A", user_id=FIRST_POST_USER, topic="Forecast intervals",
                  context="Core opinion/take: intervals beat point forecasts")

    [trace] = fake_db.tables["generation_traces"]
    record = trace["node_outputs"]["final_validation"]
    assert result["post"] == normalise_post_punctuation(draft)       # exactly what A returned before this branch
    assert count_words(result["post"]) == 101
    assert (record["words"], record["length"], record["over_by"]) == (101, "over_length", 1)
    assert "word_count_enforcer" not in [c["event_type"] for c in trace["llm_calls"]]   # A did not act on it
    assert len(claude.calls) == 6
