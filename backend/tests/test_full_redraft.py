"""Variant B's full-redraft path through run_pipeline (split out of
test_pipeline_b.py): the second review of a redraft, the code fixes made again
on it, the trim after it, and a redraft or a first draft cut off at its limit."""

import json

import pytest

from tests.length_fixtures import _cut_off, _outputs, _run
from tests.review_fixtures import answer_pipeline
from tests.test_checks import _post
from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)
from tests.test_pipeline_b import MADE_UP, UNSUPPORTED, _distinct, _events, _review

def test_the_full_redraft_is_reviewed_only_where_it_changed(claude, fake_db, seeded_kb):
    first = _distinct(37)                                             # 370 words: over, whatever code deletes
    second = _distinct(35).replace("Plainaa", "Plainzz")              # one sentence new, 34 as they were
    answer_pipeline(claude, [first, second])

    result = _run("B")

    review = _outputs(fake_db)["review_second"]
    assert (review["reused"], review["reviewed"]) == (34, 1) and _review(result) == ("fixed", [])
    assert [d["node"] for d in _outputs(fake_db)["draft_history"]] == ["draft", "redraft"]


def test_a_failed_trim_leaves_over_length_on_the_returned_post(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(36), _post(36)], trim=json.dumps({"ranking": [99]}))

    result = _run("B")

    assert _outputs(fake_db)["trim_result"]["outcome"] == "trim_failed"
    assert _review(result) == ("issues_remain", [("over_length", "")])


@pytest.mark.parametrize("ranking,outcome", [([10], "fixed"), ([11], "not_reviewed")])
def test_a_sentence_the_trim_deleted_does_not_count_against_the_post(claude, fake_db, seeded_kb, ranking, outcome):
    spec = {"changes": {10: MADE_UP}}                                 # sentence 10 never gets a valid record
    answer_pipeline(claude, [_distinct(37), _distinct(36)], reviews=[spec, spec], trim=json.dumps({"ranking": ranking}))

    result = _run("B")

    assert _outputs(fake_db)["review_second"]["unreviewed"] == [9]
    assert result["review"]["outcome"] == outcome


def test_a_cut_off_redraft_keeps_the_post_which_is_then_trimmed_and_reported(claude, fake_db, seeded_kb):
    cut = "<post>\nPlain word"
    over = f"{_post(36)}\n\nNo marker on this line."                 # 365 words
    answer_pipeline(claude, [over, _cut_off(cut)], trim=json.dumps({"ranking": [10, 11]}))

    result = _run("B")

    outputs = _outputs(fake_db)
    assert result["status"] == "ok" and outputs["review"]["redraft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert _events(fake_db)[-2:] == ["redraft", "trim"] and "draft_truncated" not in outputs
    assert [d["node"] for d in outputs["draft_history"]] == ["draft", "redraft_truncated", "trim"]
    assert outputs["final_validation"]["words"] == 345 and result["post"] == outputs["final_post"]
    assert _review(result) == ("issues_remain", [("uncited_span", "No marker on this line.")])


def test_a_cut_off_first_draft_still_returns_no_post(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_cut_off("<post>\npgvector makes retrieval")])

    result = _run("B")

    assert (result["status"], result["post"]) == ("draft_truncated", "") and "review" not in result
    assert _events(fake_db) == ["archetype", "generate"]


def test_an_under_length_post_triggers_nothing(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(5)])                 # 50 words against 250-350

    result = _run("B")

    assert _outputs(fake_db)["final_validation"]["length"] == "under_length"
    assert _events(fake_db) == ["archetype", "generate", "review", "review"] and _review(result) == ("clean", [])


def test_code_fixes_run_again_on_a_full_redraft_with_no_extra_call(claude, fake_db, seeded_kb):
    stated = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "pgvector makes retrieval fast"}
    wrong = "pgvector makes retrieval fast. [[V]]"
    first = f"{wrong}\n\n{_distinct(37)}"                            # over length whatever code does: the full redraft
    # The redraft keeps that sentence and marks it [[V]] again, and adds a sentence nothing states.
    second = f"{wrong}\n\nEveryone felt relieved. [[V]]\n\n{_distinct(30)}"
    answer_pipeline(claude, [first, second], reviews=[{"changes": {1: stated}}, {"changes": {2: UNSUPPORTED}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    record = outputs["review"]
    marker_fix = {"type": "marker_replaced", "issue": "wrong_citation", "sentence": 0,
                  "before": wrong, "after": "pgvector makes retrieval fast. [[S1]]"}
    assert record["fixes"]["code"] == [marker_fix] and record["fixes"]["route"] == "full"
    assert record["fixes_after_redraft"]["code"] == [
        marker_fix,                                                   # corrected, reverted by the redraft, corrected again
        {"type": "sentence_deleted", "issue": "not_in_sources", "sentence": 1,
         "before": "Everyone felt relieved. [[V]]", "after": None}]
    assert outputs["citations"][0]["sources"] == ["S1"] and "Everyone felt relieved" not in result["post"]
    events = _events(fake_db)
    assert events.count("redraft") == 1 and "targeted_fix" not in events      # no call added, no third draft
    assert events[-1] == "review"                                     # the redraft's review; nothing after it
    # The second review keeps the counts of what was sent; its issues are derived again in code.
    second_review = outputs["review_second"]
    assert (second_review["reviewed"], second_review["issues"], second_review["unreviewed"]) == (1, [], [])
    assert _review(result) == ("fixed", [])
    assert [item["text"] for item in record["removed"]] == ["Everyone felt relieved."]
    assert [t["step"] for t in outputs["step_timings"]][-4:] == ["review_redraft", "code_fix_redraft", "review_refixed", "outcome"]
