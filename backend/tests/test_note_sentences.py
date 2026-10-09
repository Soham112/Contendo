"""Verbatim event evidence respects note structure and literal spans."""
import json
import pytest

@pytest.mark.parametrize("note,quote", [
    ("Dr. Rao shipped the fix. We celebrated.", "Dr. Rao shipped the fix."),
    ("A. B. Rao shipped the fix. We celebrated.", "A. B. Rao shipped the fix."),
    ("We shipped in the U.S. last week. It worked.", "We shipped in the U.S. last week."),
    ("Latency fell to 3.14 seconds. We celebrated.", "Latency fell to 3.14 seconds."),
    ('She said "We shipped it." Then we celebrated.', 'She said "We shipped it."'),
    ("- We shipped the fix\n- We celebrated the result", "We shipped the fix"),
    ("We shipped the fix without drama", "We shipped the fix without drama"),
    ("Shipped", "Shipped"),
    ("1. We shipped the fix\n2. We celebrated", "We shipped the fix"),
    ("We shipped the fix\nWe celebrated the result", "We shipped the fix"),
    ("See https://example.com/a.b?q=one.two before deploying. We shipped.", "See https://example.com/a.b?q=one.two before deploying."),
    ('We ran `print("Done. Next.")` before deploying. It worked.', 'We ran `print("Done. Next.")` before deploying.'),
])
def test_full_sentence_line_and_bullet_evidence_passes(note, quote):
    from agents.archetype_agent import event_quote_failure
    from utils.sentences import note_sentences
    assert quote in note_sentences(note)
    assert event_quote_failure(quote, {"text": note}) is None

@pytest.mark.parametrize("quote,note,reason", [
    ("We built the forecast", "We built the forecasting system.", "event_quote_partial_word"),
    ("We built the forecast", "We built the forecast last spring.", "event_quote_not_sentence"),
    ("We built a different forecast.", "We built the forecast last spring.", "event_quote_not_in_note"),
])
def test_invalid_quote_reason_is_logged_and_preserved_in_draft_trace(claude, caplog, quote, note, reason):
    from agents.draft_agent import draft_node
    from tests.generation_fixtures import OWN, make_state
    claude.queue(json.dumps({"archetype": "before_after", "event_note": 1, "event_quote": quote}), "A general draft.")
    with caplog.at_level("WARNING"):
        state = draft_node(make_state([{**OWN, "text": note}]))
    decision = state["archetype_decision"]
    assert decision["archetype"] == "general"
    assert decision["event_quote"] == quote
    assert decision["reason"] == reason
    assert reason in caplog.text


def test_existing_quote_contract_rejects_partial_word_and_partial_sentence():
    from agents.archetype_agent import quote_is_in_note
    assert not quote_is_in_note("We built the forecast", {"text": "We built the forecasting system."})
    assert not quote_is_in_note("We built the forecast", {"text": "We built the forecast last spring."})


@pytest.mark.parametrize("note,quote,expected", [
    ("What happened: for the two weeks before Christmas, Kestrel under-forecast demand at the three northern depots by 18 to 26 percent.", "for the two weeks before Christmas, Kestrel under-forecast demand at the three northern depots by 18 to 26 percent.", None),
    ("What happened: for the two weeks before Christmas, Kestrel under-forecast demand at the three northern depots by 18 to 26 percent.", "What happened: for the two weeks before Christmas, Kestrel under-forecast demand at the three northern depots by 18 to 26 percent.", None),
    ("We didn't think the launch failed.", "the launch failed.", "event_quote_not_sentence"),
    ("We shipped at 10:30 without incident.", "30 without incident.", "event_quote_not_sentence"),
    ("We shipped via https://example.com/path:we shipped.", "we shipped.", "event_quote_not_sentence"),
    ("We used `label: we shipped.`", "we shipped.`", "event_quote_not_sentence"),
    ("Unexpected heading:   We shipped without incident.", "We shipped without incident.", None),
    ("Unexpected heading: We shipped without incident. Then celebrated.", "We shipped", "event_quote_not_sentence"),
])
def test_colon_quote_starts_preserve_sentence_ends(note, quote, expected):
    from agents.archetype_agent import event_quote_failure
    assert event_quote_failure(quote, {"text": note}) == expected


@pytest.mark.parametrize("note,quote,expected", [
    ("- Outcome: We shipped without incident", "We shipped without incident", None),
    ("Outcome: We shipped without incident\nNext: We celebrated", "We shipped without incident", None),
    ("Outcome: We shipped without incident. Then we celebrated.", "We shipped without incident.", None),
    ("Outcome: We shipped without incident. Then we celebrated.", "We shipped without incident. Then we celebrated.", "event_quote_not_sentence"),
    ("Outcome: We shipped the forecasting system.", "We shipped the forecast", "event_quote_partial_word"),
    ("Outcome: We shipped the forecast safely.", "We shipped the forecast", "event_quote_not_sentence"),
    ("We shipped at 10 : 30 without incident.", "30 without incident.", "event_quote_not_sentence"),
    ("We ran:\n```python\nlabel: we shipped.\n```", "we shipped.", "event_quote_not_sentence"),
])
def test_colon_candidates_respect_notes_literals_and_original_sentence_end(note, quote, expected):
    from agents.archetype_agent import event_quote_failure
    assert event_quote_failure(quote, {"text": note}) == expected
