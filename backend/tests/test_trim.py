"""Trim by deletion (variants B and C): whole sentences are deleted, chosen by
one Haiku call and removed in code. Nothing is rewritten and nothing is ever
lengthened; an answer that cannot be used leaves the post untrimmed."""

import json

import pytest

from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import OWN, make_state
from tests.length_fixtures import TRIM, _clean, _cut_off, _lines, _outputs, _post, _run
from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)
from utils.formatters import count_words, resolve_length_target


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
    from agents.trim_agent import trim_node
    from pipeline.finalise import finalise_trimmed_node

    claude.queue(*replies)
    return finalise_trimmed_node(trim_node(state))


def test_trim_deletes_the_chosen_spans_and_the_post_is_measured_again(claude):
    state = _trim_state()                       # 12 spans of 10 words: 120 against a maximum of 100
    before = state["final_post"]

    state = _trim(claude, state, json.dumps({"ranking": [3, 7]}))

    [call] = claude.calls
    assert call["model"] == TRIM and call["tool_choice"]["name"] == "rank_sentences_to_delete"
    assert state["trim_result"] == {
        "outcome": "trimmed", "reason": None, "max_words": 100, "words_before": 120, "words_after": 100,
        "ranking": [{"index": 2, "span": 2, "text": _clean(_lines(12)[2])},
                    {"index": 6, "span": 6, "text": _clean(_lines(12)[6])}],
        "deleted": [{"index": 2, "span": 2, "text": _clean(_lines(12)[2])},
                    {"index": 6, "span": 6, "text": _clean(_lines(12)[6])}],
        "kept_ranked": [],
    }
    assert state["final_post"] == "\n\n".join(_clean(l) for i, l in enumerate(_lines(12)) if i not in (2, 6))
    assert state["final_validation"]["words"] == count_words(state["final_post"]) == 100
    assert state["final_validation"]["length"] == "ok"
    assert len(state["citations"]) == 10
    for c in state["citations"]:
        assert state["final_post"][c["start"]:c["end"]] == c["text"]
    assert set(state["final_post"].split()) <= set(before.split())   # nothing written, only removed


def test_the_trim_call_sees_numbered_sentences_their_lengths_and_the_maximum(claude):
    state = _trim_state()
    _trim(claude, state, json.dumps({"ranking": [2, 3]}))

    prompt = claude.calls[0]["messages"][-1]["content"]
    for number, line in enumerate(_lines(12), 1):
        assert f"{number}. (10 words) {_clean(line)}" in prompt
    assert "120" in prompt and "100" in prompt and "20" in prompt   # length, maximum, excess


def test_a_trim_that_leaves_the_post_over_is_a_recorded_failure(claude):
    state = _trim(claude, _trim_state(), json.dumps({"ranking": [5]}))

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"] == "still_over"
    assert (state["trim_result"]["words_before"], state["trim_result"]["words_after"]) == (120, 110)
    assert [d["index"] for d in state["trim_result"]["deleted"]] == [4]
    assert state["final_validation"]["length"] == "over_length" and state["final_validation"]["over_by"] == 10
    assert state["final_validation"]["words"] == count_words(state["final_post"]) == 110
    assert len(claude.calls) == 1                                   # one bounded attempt, no second call


@pytest.mark.parametrize("delete,reason", [
    ([0], "invalid_indices"), ([13], "invalid_indices"), ([2, 99], "invalid_indices"), ([-1], "invalid_indices"),
    ([], "no_sentences_ranked"), (list(range(1, 13)), "all_sentences_ranked"),
    ([3, 3], "repeated_indices"), ([3, 7, 3], "repeated_indices"), ([5, 6, 7, 5, 6], "repeated_indices"),
])
def test_an_unusable_ranking_is_rejected_and_the_post_is_left_untrimmed(claude, delete, reason):
    state = _trim_state()
    before = state["final_post"]

    state = _trim(claude, state, json.dumps({"ranking": delete}))

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"].startswith(reason)
    assert state["trim_result"]["deleted"] == [] and state["trim_result"]["words_after"] == 120
    assert state["final_post"] == before
    assert state["final_validation"]["length"] == "over_length"


def test_deletion_stops_as_soon_as_the_post_fits_and_the_rest_of_the_ranking_is_kept(claude):
    state = _trim_state()                       # 12 sentences of 10 words: 120 against 100, so two have to go

    state = _trim(claude, state, json.dumps({"ranking": [9, 3, 7, 1, 11]}))

    result = state["trim_result"]
    assert result["outcome"] == "trimmed"
    assert [r["index"] for r in result["ranking"]] == [8, 2, 6, 0, 10]         # the whole ranking, in the order given
    assert [d["index"] for d in result["deleted"]] == [8, 2]                   # only the first two were needed
    assert [k["index"] for k in result["kept_ranked"]] == [6, 0, 10]
    assert (result["words_before"], result["words_after"]) == (120, 100)
    for kept in result["kept_ranked"]:
        assert kept["text"] in state["final_post"]
    for deleted in result["deleted"]:
        assert deleted["text"] not in state["final_post"]
    assert len(state["citations"]) == 10


def test_sentences_go_in_ranked_order_not_in_the_order_they_appear(claude):
    state = _trim(claude, _trim_state(count=11), json.dumps({"ranking": [10, 2]}))      # 110 against 100: one goes

    assert [d["index"] for d in state["trim_result"]["deleted"]] == [9]
    assert [k["index"] for k in state["trim_result"]["kept_ranked"]] == [1]
    assert _clean(_lines(11)[1]) in state["final_post"] and _clean(_lines(11)[9]) not in state["final_post"]


def test_the_post_is_measured_after_each_deletion(claude):
    # Three short sentences and one long: 8 words over. The first ranked (3 words) is not enough,
    # the second (5 more) is, and the long one ranked third is never touched.
    from pipeline.finalise import finalise_draft_node

    marked = ("Tiny one here. [[V]]\n\nA second sentence of five. [[V]]\n\n"
              + " ".join(["long"] * 20) + ". [[V]]\n\n" + _post(8))
    state = finalise_draft_node(make_state([OWN], archetype="general", current_draft=marked,
                                           length_target={"min_words": 0, "max_words": 100, "may_expand": False, "basis": "thin_sources"}))
    assert state["final_validation"]["words"] == 108

    state = _trim(claude, state, json.dumps({"ranking": [1, 2, 3]}))

    assert [d["text"] for d in state["trim_result"]["deleted"]] == ["Tiny one here.", "A second sentence of five."]
    assert [k["index"] for k in state["trim_result"]["kept_ranked"]] == [2]
    assert state["trim_result"]["words_after"] == 100


def test_deleting_the_whole_ranking_without_fitting_is_still_over_and_keeps_the_shorter_post(claude):
    state = _trim(claude, _trim_state(count=15), json.dumps({"ranking": [4, 8, 12]}))   # 150 against 100

    result = state["trim_result"]
    assert (result["outcome"], result["reason"]) == ("trim_failed", "still_over")
    assert [d["index"] for d in result["deleted"]] == [3, 7, 11] and result["kept_ranked"] == []
    assert (result["words_before"], result["words_after"]) == (150, 120)
    assert state["final_validation"]["words"] == count_words(state["final_post"]) == 120


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

    from agents.trim_agent import trim_node
    state = trim_node(state)

    assert state["trim_result"]["outcome"] == "trim_failed"
    assert state["trim_result"]["reason"] == "api_error: InternalServerError"
    assert state["current_draft"] == before


# --- Trim works in sentences ------------------------------------------------------

# The pm-09 draft from the step 3 live check (eval trace 761234eb): 187 words
# against 100-180, with one marker per paragraph, so its smallest span is 13 words.
PM09 = [
    'Most product teams skip straight from "we want more retention" to "let\'s build a dashboard." [[V]]',
    "That gap is exactly what an opportunity solution tree is designed to close. [[S1]]",
    "The shape is simple. One outcome sits at the top. Customer needs, pains and desires branch beneath it. "
    "Solutions branch beneath each of those. Small experiments sit at the bottom, underneath each solution. [[S1]]",
    "Think of it like a decision bracket in a tournament. You can't play the final before you've played the semis. "
    "Jumping to a solution before you've named the opportunity is skipping straight to the final. [[V]]",
    "What I found sharp about this, reading a set of notes on the framework: it makes gaps obvious. If you have five "
    "solutions mapped to one opportunity and zero mapped to the rest, you can see that. No hiding. [[S1]]",
    "The honest weakness? It can balloon into a wall of sticky notes that nobody updates. [[S1]]",
    "The notes suggested keeping it to one outcome per quarter, which sounds like the right trade to make. [[S1]]",
    'Watch for the moment your team says "let\'s just build it." That\'s usually where the tree would\'ve helped most. [[V]]',
]


def _pm09_state():
    from pipeline.finalise import finalise_draft_node

    return finalise_draft_node(make_state([OWN], archetype="teach_me_something", current_draft="\n\n".join(PM09),
                                          length_target=resolve_length_target("linkedin post", "concise")))


def _numbered(claude) -> list[str]:
    prompt = claude.calls[-1]["messages"][-1]["content"]
    return prompt[prompt.index("<post>") + 7:prompt.index("</post>")].strip().splitlines()


def test_a_post_seven_words_over_is_met_by_deleting_less_than_its_smallest_span(claude):
    state = _pm09_state()
    assert (state["final_validation"]["words"], state["final_validation"]["over_by"]) == (187, 7)
    smallest_span = min(count_words(c["text"]) for c in state["citations"])
    assert smallest_span == 13                                   # deleting any whole span costs 13 words or more

    # Sentence 3 is "The shape is simple." (4 words); sentence 14 is "The honest weakness?" (3 words).
    state = _trim(claude, state, json.dumps({"ranking": [3, 14]}))

    assert state["trim_result"]["outcome"] == "trimmed"
    assert [(d["index"], d["span"], d["text"]) for d in state["trim_result"]["deleted"]] == [
        (2, 2, "The shape is simple."), (13, 5, "The honest weakness?")]
    assert (state["trim_result"]["words_before"], state["trim_result"]["words_after"]) == (187, 180)
    assert 187 - 180 < smallest_span
    assert state["final_validation"]["length"] == "ok"
    assert "One outcome sits at the top. Customer needs" in state["final_post"]
    assert "\n\nIt can balloon into a wall of sticky notes that nobody updates.\n\n" in state["final_post"]


def test_the_trim_call_numbers_every_sentence_of_every_span(claude):
    state = _pm09_state()
    _trim(claude, state, json.dumps({"ranking": [3]}))

    numbered = _numbered(claude)
    assert len(numbered) == 18                                    # 8 spans, 18 sentences
    assert numbered[0].startswith("1. (15 words) Most product teams")
    assert numbered[2] == "3. (4 words) The shape is simple."
    assert numbered[12] == "13. (2 words) No hiding."
    assert numbered[13] == "14. (3 words) The honest weakness?"
    assert numbered[17] == "18. (8 words) That's usually where the tree would've helped most."


def test_kept_sentences_of_a_span_stay_one_span_with_its_citation(claude):
    state = _pm09_state()
    before = [(c["basis"], c["sources"]) for c in state["citations"]]

    state = _trim(claude, state, json.dumps({"ranking": [3, 14]}))

    assert [(c["basis"], c["sources"]) for c in state["citations"]] == before      # same 8 spans, same citations
    assert state["citations"][2]["text"].startswith("One outcome sits at the top.")
    assert state["citations"][5]["text"] == "It can balloon into a wall of sticky notes that nobody updates."
    for c in state["citations"]:
        assert state["final_post"][c["start"]:c["end"]] == c["text"]


def test_deleting_every_sentence_of_a_span_removes_the_span_and_its_line(claude):
    state = _trim(claude, _pm09_state(), json.dumps({"ranking": [14, 15]}))        # both sentences of span 6

    assert len(state["citations"]) == 7
    assert "honest weakness" not in state["final_post"] and "sticky notes" not in state["final_post"]
    assert "\n\n\n" not in state["final_post"]
    assert [d["span"] for d in state["trim_result"]["deleted"]] == [5, 5]


def test_each_sentence_inherits_its_spans_citation():
    from utils.citations import strip_citations
    from utils.sentences import split_spans

    spans = strip_citations("First from one. Second from one. [[S1]] A view. Another view. [[V]]\n"
                            "Both say this. And this. [[S1,S3]] You asked. [[R]] No marker here. None here either.").spans

    assert [(position, s.text, s.basis, s.sources) for position, s in split_spans(spans)] == [
        (0, "First from one.", "sources", ("S1",)), (0, "Second from one.", "sources", ("S1",)),
        (1, "A view.", "view", ()), (1, "Another view.", "view", ()),
        (2, "Both say this.", "sources", ("S1", "S3")), (2, "And this.", "sources", ("S1", "S3")),
        (3, "You asked.", "request", ()),
        (4, "No marker here.", "uncited", ()), (4, "None here either.", "uncited", ()),
    ]


def test_sentence_offsets_index_the_post():
    from utils.citations import strip_citations
    from utils.sentences import split_spans

    stripped = strip_citations("1. First point here. And more. [[V]]\n\nDr. Rao agreed in the U.S. last week. It held. [[S1]]")

    sentences = [s for _, s in split_spans(stripped.spans)]
    assert [s.text for s in sentences] == ["1. First point here.", "And more.", "Dr. Rao agreed in the U.S. last week.", "It held."]
    for sentence in sentences:
        assert stripped.text[sentence.start:sentence.end] == sentence.text


def test_code_and_urls_are_never_split_or_numbered(claude):
    from pipeline.finalise import finalise_draft_node

    marked = ("We ran `print(\"Done. Next.\")` before the deploy. It passed. [[S1]]\n\n"
              "```python\nprint('Stop. Go. Wait.')\n```\n\n"
              "The write-up is at https://example.com/a.b?q=one.two for anyone curious. Worth a read. [[S1]]\n\n"
              + _post(10))
    state = finalise_draft_node(make_state([OWN], archetype="general", current_draft=marked,
                                           length_target={"min_words": 0, "max_words": 120, "may_expand": False, "basis": "thin_sources"}))
    words_before = state["final_validation"]["words"]

    state = _trim(claude, state, json.dumps({"ranking": [2, 4]}))               # "It passed." and "Worth a read."

    numbered = _numbered(claude)
    assert len(numbered) == 14                                                 # 2 + 2 + 10 sentences: the code block has none
    assert numbered[0] == '1. (7 words) We ran `print("Done. Next.")` before the deploy.'
    assert numbered[1] == "2. (2 words) It passed."
    assert numbered[2] == "3. (8 words) The write-up is at https://example.com/a.b?q=one.two for anyone curious."
    assert not any("Stop. Go. Wait." in line for line in numbered)
    assert "```python\nprint('Stop. Go. Wait.')\n```" in state["final_post"]       # untouched
    assert [d["text"] for d in state["trim_result"]["deleted"]] == ["It passed.", "Worth a read."]
    assert state["trim_result"]["words_after"] == words_before - 5
    assert 'We ran `print("Done. Next.")` before the deploy.\n\n```python' in state["final_post"]


def test_multi_sentence_spans_are_counted_and_trigger_nothing(claude, fake_db, seeded_kb):
    state = _pm09_state()
    assert state["multi_sentence_spans"] == 5                                  # spans 3, 4, 5, 6 and 8 of the eight

    one_each = "\n\n".join(_lines(30))                                        # 30 spans of one sentence each, 300 words
    claude.queue(ARCHETYPE_GENERAL, one_each)
    _run("B", quality="draft")
    assert _outputs(fake_db)["multi_sentence_spans"] == 0

    fake_db.tables["generation_traces"].clear()
    paired = "\n\n".join(f"{a.removesuffix(' [[V]]')}. {b}" for a, b in zip(_lines(15), _lines(15)))
    claude.queue(ARCHETYPE_GENERAL, paired)                                    # 15 spans of two sentences each
    _run("C")
    assert _outputs(fake_db)["multi_sentence_spans"] == 15
    assert len(claude.calls) == 4                                              # two runs of two calls: the count changed nothing
