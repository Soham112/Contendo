"""Closed-vocabulary punctuation normalization at both post output boundaries."""

import pytest


@pytest.mark.parametrize("raw,expected", [
    ("It was slow—then faster.", "It was slow, then faster."),
    ("It was slow — Then faster.", "It was slow. Then faster."),
    ("It was slow\t—  then faster.", "It was slow, then faster."),
    ("First—then—Finally.", "First, then. Finally."),
    ("First — Élan follows.", "First. Élan follows."),
    ("First paragraph.\n\nNext—then last.", "First paragraph.\n\nNext, then last."),
    ("Hyphen-word, en–dash, minus − sign.", "Hyphen-word, en–dash, minus − sign."),
    ("Already clean.\n\nKeep spacing.", "Already clean.\n\nKeep spacing."),
    ("", ""),
])
def test_finalization_normalizes_only_em_dashes(raw, expected):
    from pipeline.graph import finalize_node

    state = finalize_node({"current_draft": raw})
    assert state["final_post"] == expected
    assert state["current_draft"] == raw


@pytest.mark.parametrize("reply,expected", [
    ("It crawled—then recovered.", "It crawled, then recovered."),
    ("It crawled  —  Then recovered.", "It crawled. Then recovered."),
    ("It crawled–then recovered.", "It crawled–then recovered."),
])
def test_successful_selection_refine_normalizes_em_dashes(claude, fake_db, reply, expected):
    from agents.refine_agent import refine_selection

    from tests.test_refine_selection import _seed_trace
    trace_id = _seed_trace(fake_db)
    claude.queue(reply)
    result = refine_selection("It was slow.", "Make it punchier", "It was slow.", user_id="user-a", trace_id=trace_id)
    assert result["status"] == "ok"
    assert result["rewritten_text"] == expected
    assert len(claude.calls) == 1


@pytest.mark.parametrize("literal", [
    "10—20", "`value—Next`", "https://example.com/a—b", '[link](https://example.com/a—b)',
    '```python\nvalue = "a—B"\n```', '    value = "a—B"', '"literal—value"',
])
def test_finalize_and_refine_preserve_literal_data(claude, fake_db, literal):
    from agents.refine_agent import refine_selection
    from pipeline.graph import finalize_node
    from tests.test_refine_selection import _seed_trace
    raw = f"First—then done.\n\n{literal}"
    expected_literal = "10–20" if literal == "10—20" else literal
    expected = f"First, then done.\n\n{expected_literal}"
    assert finalize_node({"current_draft": raw})["final_post"] == expected
    trace_id = _seed_trace(fake_db)
    claude.queue(raw)
    result = refine_selection(raw, "Improve flow", raw, user_id="user-a", trace_id=trace_id)
    assert result["rewritten_text"] == expected


@pytest.mark.parametrize("raw,expected", [
    ("2019—2023", "2019–2023"),
    ("2019-01-01—2023-12-31", "2019-01-01–2023-12-31"),
])
def test_year_and_iso_date_ranges_at_both_output_boundaries(claude, fake_db, raw, expected):
    from agents.refine_agent import refine_selection
    from pipeline.graph import finalize_node
    from tests.test_refine_selection import _seed_trace
    assert finalize_node({"current_draft": raw})["final_post"] == expected
    claude.queue(raw)
    result = refine_selection(raw, "Improve flow", raw, user_id="user-a", trace_id=_seed_trace(fake_db))
    assert result["rewritten_text"] == expected
