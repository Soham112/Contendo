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
def test_successful_selection_refine_normalizes_em_dashes(claude, reply, expected):
    from agents.refine_agent import refine_selection

    claude.queue(reply)
    result = refine_selection("It was slow.", "Make it punchier", "It was slow.", user_id="user-a")
    assert result["status"] == "ok"
    assert result["rewritten_text"] == expected
    assert len(claude.calls) == 1
