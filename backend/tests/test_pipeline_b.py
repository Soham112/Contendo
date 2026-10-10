"""Variant B through run_pipeline: the review, the one redraft, the second
review of what changed, and how the run is reported. The model is the fake;
whether the review's observations are right is measured on real calls, not here.
What the redraft is told is tested in test_redraft.py."""

import json

import pytest

from tests.length_fixtures import KB_USER, _clean, _cut_off, _outputs, _run
from tests.review_fixtures import answer_pipeline, assigned
from tests.test_checks import _lines, _post
from tests.test_generation_trace import STANDARD_RUN, seeded_kb  # noqa: F401  (shared fixture)

SOURCED = "pgvector makes retrieval fast. [[S1]]"
VIEW = "That is most of the argument. [[V]]"
CLEAN = f"{SOURCED}\n\n{VIEW}"
UNCITED = f"{CLEAN}\n\nNo marker on this line."
MARKED_NOW = f"{CLEAN}\n\nThe line has a marker now. [[V]]"
# A sentence record that states a fact nothing supports: not_in_sources.
UNSUPPORTED = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")
RHYTHM_WHY = "Reads like a slogan."
REQUEST = {"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"}


def _events(fake_db) -> list[str]:
    [trace] = fake_db.tables["generation_traces"]
    return [call["event_type"] for call in trace["llm_calls"]]


def _types(issues: list[dict]) -> list[str]:
    return [issue["type"] for issue in issues]


# --- Clean, fixed, issues_remain ------------------------------------------------

def test_a_clean_draft_is_one_draft_and_one_review_and_no_redraft(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert result["review"] == {"outcome": "clean", "issues": []}
    assert outputs["review"]["first"]["acting"] == [] and "redraft" not in outputs["review"]
    assert "review_second" not in outputs
    assert (outputs["review_first"]["reviewed"], outputs["review_first"]["reused"]) == (2, 0)
    assert result["post"] == _clean(CLEAN)


def test_an_acting_issue_gets_exactly_one_redraft_and_a_second_review(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, MARKED_NOW])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate", "review", "redraft", "review"]
    assert _types(outputs["review"]["first"]["acting"]) == ["uncited_span"]
    assert outputs["review"]["second"]["acting"] == []
    assert result["review"] == {"outcome": "fixed", "issues": []}
    assert [d["node"] for d in outputs["draft_history"]] == ["draft", "redraft"]
    assert result["post"] == outputs["final_post"] == _clean(MARKED_NOW)
    assert outputs["checks_final"] == {"issues": [], "counts": {}}       # the returned post's checks
    assert outputs["review"]["first"]["checks"]["counts"] == {"uncited_span": 1}


def test_issues_after_the_redraft_remain_and_there_is_never_a_third_draft(claude, fake_db, seeded_kb):
    prompts = answer_pipeline(claude, [UNCITED, f"{CLEAN}\n\nStill no marker here."])

    result = _run("B")

    assert len(prompts) == 2 and _events(fake_db).count("redraft") == 1
    assert result["status"] == "ok" and "Still no marker here." in result["post"]     # nothing is silently removed
    assert result["review"] == {"outcome": "issues_remain",
                                "issues": [{"type": "uncited_span", "sentence_text": "Still no marker here."}]}
    assert _outputs(fake_db)["review"]["outcome"] == "issues_remain"


def test_a_review_issue_triggers_the_redraft(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN, SOURCED], reviews=[{"changes": {2: UNSUPPORTED}}])

    result = _run("B")

    [issue] = _outputs(fake_db)["review"]["first"]["acting"]
    assert (issue["type"], issue["origin"], issue["text"]) == ("not_in_sources", "review", "That is most of the argument.")
    assert result["review"]["outcome"] == "fixed" and result["post"] == "pgvector makes retrieval fast."


def test_record_only_issues_alone_cause_no_redraft(claude, fake_db, seeded_kb):
    changed = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "pgvector makes retrieval fast",
               "detail_change": {"source_words": "fast", "post_words": "quick"}}
    answer_pipeline(claude, [f"pgvector makes retrieval quick. [[S1]]\n\n{VIEW}"],
                    reviews=[{"changes": {1: changed}, "rhythm": {2: {"sentence": 2, "why": RHYTHM_WHY}}}])

    result = _run("B")

    first = _outputs(fake_db)["review"]["first"]
    assert _types(first["recorded"]) == ["changed_detail", "ai_rhythm"] and first["acting"] == []
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert result["review"] == {"outcome": "clean", "issues": []}


# --- not_reviewed ------------------------------------------------------------------

def test_a_failed_first_review_still_redrafts_and_the_second_review_decides_the_outcome(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, MARKED_NOW], reviews=[{"replace": {1: "not a tool call"}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert outputs["review_first"]["outcome"] == "not_reviewed" and "error" in outputs["review_first"]
    assert outputs["review_first"]["unreviewed"] == [0, 1, 2]
    assert _types(outputs["review"]["first"]["acting"]) == ["uncited_span"]      # the deterministic issue still acts
    # The failed review call was tried twice (llm.client.complete_structured); then one redraft, one review.
    assert _events(fake_db) == ["archetype", "generate", "review", "review", "redraft", "review"]
    # Nothing to reuse from a review that did not happen: every sentence of the redraft is sent.
    second = outputs["review_second"]
    assert (second["outcome"], second["reviewed"], second["reused"], second["unreviewed"]) == ("clean", 3, 0, [])
    # The returned post was fully reviewed, so the outcome is that review's.
    assert result["review"] == {"outcome": "fixed", "issues": []}
    assert outputs["review"]["unreviewed"] == []


def test_a_failed_first_review_does_not_hide_issues_the_second_review_finds(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, MARKED_NOW],
                    reviews=[{"replace": {1: "not a tool call"}}, {"changes": {2: UNSUPPORTED}}])

    result = _run("B")

    assert result["review"] == {"outcome": "issues_remain",
                                "issues": [{"type": "not_in_sources", "sentence_text": "That is most of the argument."}]}


@pytest.mark.parametrize("failed_pass", [0, 1])
def test_a_returned_post_whose_own_review_failed_is_not_reviewed(claude, fake_db, seeded_kb, failed_pass):
    reviews = [{}, {}]
    reviews[failed_pass] = {"replace": {1: "not a tool call"}}
    # First case: nothing acts, so the unreviewed first draft is returned. Second: the redraft's review fails.
    drafts = [CLEAN] if failed_pass == 0 else [UNCITED, f"A new opening line. [[V]]\n\n{MARKED_NOW}"]
    answer_pipeline(claude, drafts, reviews=reviews)

    result = _run("B")

    assert result["review"]["outcome"] == "not_reviewed"
    assert _events(fake_db).count("redraft") == failed_pass
    assert _outputs(fake_db)["review"]["unreviewed"]                  # the sentences nothing reviewed are named


def test_one_sentence_with_no_valid_record_makes_the_post_not_reviewed(claude, fake_db, seeded_kb):
    made_up = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "words that are not in the source"}
    answer_pipeline(claude, [CLEAN], reviews=[{"changes": {1: made_up}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert [i["reason"] for i in outputs["review_first"]["invalid"]] == ["evidence_not_in_source"]
    assert outputs["review_first"]["unreviewed"] == [0]
    assert outputs["review"]["unreviewed"] == ["pgvector makes retrieval fast."]
    assert result["review"] == {"outcome": "not_reviewed", "issues": []}        # never clean
    assert _events(fake_db).count("redraft") == 0


def test_a_sentence_with_no_valid_record_is_sent_again_and_never_reused(claude, fake_db, seeded_kb):
    made_up = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "words that are not in the source"}
    answer_pipeline(claude, [UNCITED, MARKED_NOW], reviews=[{"changes": {1: made_up}}])

    result = _run("B")

    second = _outputs(fake_db)["review_second"]
    assert (second["reused"], second["reviewed"], second["unreviewed"]) == (1, 2, [])    # sentences 1 and 3 were sent
    assert result["review"] == {"outcome": "fixed", "issues": []}


def test_a_sentence_without_a_record_that_the_trim_deleted_does_not_count(claude, fake_db, seeded_kb):
    made_up = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "words that are not in the source"}
    spec = {"changes": {10: made_up}}
    # 36 different ten-word lines (360 words), so each sentence of the redraft matches its own earlier one.
    post = "\n\n".join(line.replace("Plain", f"Plain{chr(97 + n // 26)}{chr(97 + n % 26)}") for n, line in enumerate(_lines(36)))
    answer_pipeline(claude, [post, post], reviews=[spec, spec], trim=json.dumps({"ranking": [10]}))

    result = _run("B")

    assert _outputs(fake_db)["review_second"]["unreviewed"] == [9]
    assert result["review"] == {"outcome": "fixed", "issues": []}


# --- The second review ----------------------------------------------------------------

def test_the_second_review_sends_only_new_or_changed_sentences(claude, fake_db, seeded_kb):
    first = "\n\n".join(["One plain line. [[V]]", "Another plain line. [[V]]", SOURCED, "A fourth plain line. [[V]]",
                         "No marker on this line.", "The closing line. [[V]]"])
    second = "\n\n".join(["One  plain line. [[V]]",                 # whitespace only: the same sentence
                          "Another plain line, reworded. [[V]]",    # new text
                          SOURCED, "A fourth plain line. [[V]]",
                          "This line has its marker. [[V]]",        # new text
                          "The closing line. [[S1]]"])              # same text, another citation
    answer_pipeline(claude, [first, second],
                    reviews=[{"changes": {1: UNSUPPORTED}, "rhythm": {4: {"sentence": 4, "why": RHYTHM_WHY}}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    [second_call] = [c for c in claude.calls if (c.get("tool_choice") or {}).get("name") == "record_review"][-1:]
    assert assigned(second_call) == [2, 5, 6]
    assert "Your assignment: sentences 2, 5, 6. Record exactly one entry for each of them (3 in all)" in (
        second_call["messages"][-1]["content"])
    assert (outputs["review_second"]["reused"], outputs["review_second"]["reviewed"]) == (3, 3)
    assert [r["sentence"] for r in outputs["review_second"]["records"]] == [1, 2, 3, 4, 5, 6]
    # A reused record gives the issue it gave before, and its rhythm note comes with it.
    assert [(i["type"], i["sentence"]) for i in outputs["review_second"]["issues"]] == [("not_in_sources", 0), ("ai_rhythm", 3)]
    assert result["review"] == {"outcome": "issues_remain",
                                "issues": [{"type": "not_in_sources", "sentence_text": "One  plain line."}]}


def test_a_repeated_sentence_is_matched_to_its_own_earlier_occurrence(claude, fake_db, seeded_kb):
    repeated = "The same plain line. [[V]]"
    first = "\n\n".join([repeated, repeated, "No marker on this line."])
    second = "\n\n".join([repeated, repeated, repeated])               # a third occurrence has no counterpart
    answer_pipeline(claude, [first, second], reviews=[{"changes": {2: UNSUPPORTED}}])

    _run("B")

    review = _outputs(fake_db)["review_second"]
    assert (review["reused"], review["reviewed"]) == (2, 1)
    assert [(i["type"], i["sentence"]) for i in review["issues"]] == [("not_in_sources", 1)]


def test_a_redraft_that_changes_no_sentence_costs_no_second_review_call(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, CLEAN])                       # the uncited line was left out

    _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate", "review", "redraft"]
    assert (outputs["review_second"]["reused"], outputs["review_second"]["reviewed"], outputs["review_second"]["groups"]) == (2, 0, 0)
    assert outputs["review"]["outcome"] == "fixed"


# --- Length -------------------------------------------------------------------------

def test_a_post_still_over_length_after_the_redraft_is_trimmed(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(36), _post(36)], trim=json.dumps({"ranking": [10]}))    # 360 words against 250-350

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _types(outputs["review"]["first"]["acting"]) == ["over_length"]
    assert _types(outputs["review"]["second"]["acting"]) == ["over_length"]
    assert _events(fake_db)[-2:] == ["redraft", "trim"] and _events(fake_db).count("redraft") == 1
    assert outputs["trim_result"]["outcome"] == "trimmed"
    assert outputs["final_validation"]["words"] == 350 and outputs["checks_final"]["issues"] == []
    assert result["review"] == {"outcome": "fixed", "issues": []}            # the returned post has no acting issue


def test_a_failed_trim_leaves_over_length_on_the_returned_post(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(36), _post(36)], trim=json.dumps({"ranking": [99]}))

    result = _run("B")

    assert _outputs(fake_db)["trim_result"]["outcome"] == "trim_failed"
    assert result["review"] == {"outcome": "issues_remain", "issues": [{"type": "over_length", "sentence_text": ""}]}


@pytest.mark.parametrize("ranking,outcome", [([10], "fixed"), ([11], "issues_remain")])
def test_an_issue_on_a_sentence_the_trim_deleted_is_not_reported(claude, fake_db, seeded_kb, ranking, outcome):
    answer_pipeline(claude, [_post(36), _post(36)], reviews=[{"changes": {10: UNSUPPORTED}}],
                    trim=json.dumps({"ranking": ranking}))

    result = _run("B")

    assert result["review"]["outcome"] == outcome
    assert _types(result["review"]["issues"]) == ([] if outcome == "fixed" else ["not_in_sources"])


def test_an_under_length_post_triggers_no_redraft(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(5)])                 # 50 words against 250-350

    result = _run("B")

    assert _outputs(fake_db)["final_validation"]["length"] == "under_length"
    assert _events(fake_db).count("redraft") == 0 and result["review"]["outcome"] == "clean"


def test_a_cut_off_redraft_returns_the_first_draft_with_its_issues(claude, fake_db, seeded_kb):
    cut = "pgvector makes retrieval"
    answer_pipeline(claude, [UNCITED, _cut_off(cut)], reviews=[{"changes": {2: UNSUPPORTED}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert (result["status"], result["post"]) == ("ok", _clean(UNCITED))        # the first draft, finalised
    assert result["review"] == {"outcome": "issues_remain", "issues": [
        {"type": "uncited_span", "sentence_text": "No marker on this line."},
        {"type": "not_in_sources", "sentence_text": "That is most of the argument."}]}
    assert outputs["review"]["redraft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert "draft_truncated" not in outputs and "review_second" not in outputs and "second" not in outputs["review"]
    assert _events(fake_db) == ["archetype", "generate", "review", "redraft"]   # no second review, no third draft
    assert [(d["node"], d["text"]) for d in outputs["draft_history"]] == [("draft", UNCITED), ("redraft_truncated", cut)]
    assert outputs["final_post"] == result["post"] and outputs["checks_final"]["counts"] == {"uncited_span": 1}


def test_a_cut_off_redraft_of_an_over_length_draft_still_trims_the_first_draft(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_post(36), _cut_off("Plain word")], trim=json.dumps({"ranking": [10]}))

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db)[-2:] == ["redraft", "trim"]
    assert outputs["trim_result"]["outcome"] == "trimmed" and outputs["final_validation"]["words"] == 350
    assert result["post"] == outputs["final_post"] and outputs["checks_final"]["issues"] == []
    assert "redraft_truncated" in outputs["review"]
    assert result["review"] == {"outcome": "fixed", "issues": []}               # the trim left no acting issue


def test_a_cut_off_first_draft_still_returns_no_post(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_cut_off("pgvector makes retrieval")])

    result = _run("B")

    assert (result["status"], result["post"]) == ("draft_truncated", "") and "review" not in result
    assert _events(fake_db) == ["archetype", "generate"]


# --- The response and the trace -------------------------------------------------------

def test_the_response_lists_acting_issue_types_only(claude, fake_db, seeded_kb, client, auth_headers, monkeypatch):
    monkeypatch.setenv("PIPELINE_VARIANT", "B")
    # The redraft leaves both sentences as they were, so both records are reused.
    answer_pipeline(claude, [CLEAN, CLEAN],
                    reviews=[{"changes": {2: UNSUPPORTED}, "rhythm": {1: {"sentence": 1, "why": RHYTHM_WHY}}}])

    body = client.post("/generate", json=REQUEST, headers=auth_headers(KB_USER)).json()

    assert body["review"] == {"outcome": "issues_remain",
                              "issues": [{"type": "not_in_sources", "sentence_text": "That is most of the argument."}]}
    assert (body["status"], body["scored"], body["score"]) == ("ok", False, 0)
    second = _outputs(fake_db)["review"]["second"]
    assert _types(second["recorded"]) == ["ai_rhythm"]               # recorded in the trace, never returned
    assert RHYTHM_WHY not in json.dumps(body)


def test_the_trace_records_both_passes_the_entries_and_each_step(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, MARKED_NOW])

    _run("B")

    outputs = _outputs(fake_db)
    assert set(outputs["review"]) == {"first", "redraft", "second", "remaining", "unreviewed", "outcome"}
    redraft = outputs["review"]["redraft"]
    assert [(e["type"], e["material"]) for e in redraft["entries"]] == [("uncited_span", [["Text", "No marker on this line."]])]
    assert (redraft["input_tokens"], redraft["output_tokens"]) == (10, 10)
    assert outputs["review_first"]["input_tokens"] == outputs["review_second"]["input_tokens"] == 10
    assert [t["step"] for t in outputs["step_timings"]] == [
        "structure", "draft", "strip", "finalise", "checks", "review_draft", "decide",
        "redraft", "strip_redraft", "finalise_redraft", "checks_redraft", "review_redraft", "outcome"]
    assert all(t["seconds"] >= 0 for t in outputs["step_timings"])


# --- Quality, and the other variants -----------------------------------------------------

def test_quality_draft_under_b_runs_as_c_does(claude, fake_db, seeded_kb):
    claude.queue('{"archetype": "general"}', UNCITED)        # two calls and no more: an unqueued call fails

    result = _run("B", quality="draft")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate"]
    assert result["review"] is None and not {"review", "review_first", "review_second"} & set(outputs)
    assert outputs["checks_final"]["counts"] == {"uncited_span": 1}          # recorded, not acted on


def test_quality_polished_under_b_is_standard_b_with_no_scorer(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED, MARKED_NOW])

    result = _run("B", quality="polished")

    assert _events(fake_db) == ["archetype", "generate", "review", "redraft", "review"]
    assert (result["scored"], result["score"], result["review"]["outcome"]) == (False, 0, "fixed")


def test_variant_c_makes_no_review_call_and_no_redraft(claude, fake_db, seeded_kb):
    claude.queue('{"archetype": "general"}', UNCITED)

    result = _run("C")

    assert _events(fake_db) == ["archetype", "generate"]
    assert result["review"] is None and "No marker on this line." in result["post"]
    assert not {"review", "review_first", "step_timings"} & set(_outputs(fake_db))


def test_variant_a_returns_no_review(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    result = _run("A")

    assert result["review"] is None and result["post"] == "Final text."
