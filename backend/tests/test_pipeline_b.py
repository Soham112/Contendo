"""Variant B through run_pipeline: the review, which single path the issues
take (code fixes only, a targeted fix, or the one full redraft), the second
review, and how the run is reported. The model is the fake; whether the
review's observations are right is measured on real calls, not here. The fixes
themselves are in test_fixes.py, and what a model is told in test_redraft.py."""

import json

import pytest

from tests.length_fixtures import KB_USER, _clean, _cut_off, _outputs, _run
from tests.review_fixtures import answer_pipeline, enveloped, fixes_reply
from tests.test_checks import _lines, _post
from tests.test_generation_trace import STANDARD_RUN, seeded_kb  # noqa: F401  (shared fixture)

SOURCED = "pgvector makes retrieval fast. [[S1]]"
VIEW = "That is most of the argument. [[V]]"
CLEAN = f"{SOURCED}\n\n{VIEW}"
UNCITED = f"{CLEAN}\n\nNo marker on this line."
MARKED_NOW = f"{CLEAN}\n\nThe line has a marker now. [[V]]"
FIX_LINE_3 = fixes_reply({3: "The line has a marker now. [[V]]"})
# A sentence record that states a fact nothing supports: not_in_sources, on the whole sentence.
UNSUPPORTED = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")
# A record whose evidence is not in its source: invalid, so the sentence has no valid record.
MADE_UP = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "words that are not in the source"}
RHYTHM_WHY = "Reads like a slogan."
REQUEST = {"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"}
NOT_A_TOOL_CALL = {"replace": {1: "not a tool call"}}


def _events(fake_db) -> list[str]:
    [trace] = fake_db.tables["generation_traces"]
    return [call["event_type"] for call in trace["llm_calls"]]


def _types(issues: list[dict]) -> list[str]:
    return [issue["type"] for issue in issues]


def _review(result: dict) -> tuple:
    return result["review"]["outcome"], [(i["type"], i["sentence_text"]) for i in result["review"]["issues"]]


def _distinct(count: int) -> str:
    """count different ten-word lines with no digit in them (360 words for 36)."""
    return "\n\n".join(line.replace("Plain", f"Plain{chr(97 + n // 26)}{chr(97 + n % 26)}")
                       for n, line in enumerate(_lines(count)))


# --- No acting issue ------------------------------------------------------------------

def test_a_clean_draft_is_one_draft_and_one_review_and_nothing_else(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert result["review"] == {"outcome": "clean", "issues": [], "removed": []}
    assert outputs["review"]["first"]["acting"] == [] and not {"fixes", "targeted", "redraft"} & set(outputs["review"])
    assert "review_second" not in outputs and "draft_format" not in outputs
    assert result["post"] == _clean(CLEAN)


def test_record_only_issues_alone_cause_no_fix(claude, fake_db, seeded_kb):
    changed = {**UNSUPPORTED, "supported_by": ["S1"], "evidence": "pgvector makes retrieval fast",
               "detail_change": {"source_words": "fast", "post_words": "quick"}}
    answer_pipeline(claude, [f"pgvector makes retrieval quick. [[S1]]\n\n{VIEW}"],
                    reviews=[{"changes": {1: changed}, "rhythm": {2: {"sentence": 2, "why": RHYTHM_WHY}}}])

    result = _run("B")

    first = _outputs(fake_db)["review"]["first"]
    assert _types(first["recorded"]) == ["changed_detail", "ai_rhythm"] and first["acting"] == []
    assert _events(fake_db) == ["archetype", "generate", "review"] and _review(result) == ("clean", [])


def test_text_outside_the_envelope_is_dropped_before_the_review_and_recorded(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [f"Here you go.\n\n---\n\n<post>\n{CLEAN}\n</post>"])

    result = _run("B")

    assert result["post"] == _clean(CLEAN) and _review(result) == ("clean", [])
    assert _outputs(fake_db)["draft_format"] == [
        {"draft": "draft", "kind": "text_outside_tags", "text": "Here you go.\n\n---"}]


# --- The routing rule: one path at most -----------------------------------------------

def test_sentence_level_issues_take_the_targeted_path_and_never_a_redraft(claude, fake_db, seeded_kb):
    prompts = answer_pipeline(claude, [UNCITED], fixes=FIX_LINE_3)

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix", "review"]
    assert record["fixes"]["route"] == "targeted" and "redraft" not in record and len(prompts) == 2
    assert result["post"] == _clean(MARKED_NOW) and _review(result) == ("fixed", [])


def test_a_post_still_over_length_after_the_code_fixes_takes_the_full_redraft(claude, fake_db, seeded_kb):
    over = f"{_post(36)}\n\nNo marker on this line."                 # 365 words against 250-350, and an uncited line
    answer_pipeline(claude, [over, _post(36)], trim=json.dumps({"ranking": [10]}))

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert record["fixes"]["route"] == "full" and "targeted" not in record
    # The one redraft gets every remaining problem, the sentence-level one included.
    assert _types(record["redraft"]["entries"]) == ["uncited_span", "over_length"]
    events = _events(fake_db)
    assert events.count("redraft") == 1 and "targeted_fix" not in events and events[-2:] == ["redraft", "trim"]
    assert _outputs(fake_db)["final_validation"]["words"] == 350 and _review(result) == ("fixed", [])


def test_over_length_that_the_code_deletions_fix_needs_no_redraft(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_distinct(36)], reviews=[{"changes": {5: UNSUPPORTED}}])     # 360 words; one sentence goes

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _types(outputs["review"]["first"]["acting"]) == ["over_length", "not_in_sources"]
    assert outputs["review"]["fixes"]["route"] == "none" and outputs["final_validation"]["words"] == 350
    assert {"redraft", "targeted_fix", "trim"} & set(_events(fake_db)) == set()
    assert _review(result) == ("fixed", [])


def test_issues_that_remain_are_reported_and_there_is_never_a_second_fix(claude, fake_db, seeded_kb):
    prompts = answer_pipeline(claude, [UNCITED], fixes=fixes_reply({3: "Still no marker here."}))

    result = _run("B")

    assert len(prompts) == 2                                         # the draft and one targeted fix
    assert result["status"] == "ok" and "No marker on this line." in result["post"]     # nothing is silently removed
    assert _review(result) == ("issues_remain", [("uncited_span", "No marker on this line.")])


def test_an_issue_about_no_one_sentence_cannot_be_fixed_and_remains(claude, fake_db, seeded_kb, monkeypatch):
    from memory import profile_store

    profile = {**profile_store.load_profile(user_id=KB_USER), "words_to_avoid": ["synergy"]}
    monkeypatch.setattr("pipeline.graph.load_profile", lambda user_id: profile)
    answer_pipeline(claude, [f"## Retrieval synergy\n\n{CLEAN}"])

    result = _run("B")

    fixes = _outputs(fake_db)["review"]["fixes"]
    assert (fixes["route"], _types(fixes["unplaced"])) == ("none", ["banned_text"])
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert _review(result) == ("issues_remain", [("banned_text", "synergy")])


# --- not_reviewed: about the returned post --------------------------------------------

def test_a_failed_first_review_still_fixes_and_the_second_review_decides_the_outcome(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], reviews=[NOT_A_TOOL_CALL], fixes=FIX_LINE_3)

    result = _run("B")

    outputs = _outputs(fake_db)
    assert outputs["review_first"]["outcome"] == "not_reviewed" and outputs["review_first"]["unreviewed"] == [0, 1, 2]
    assert _types(outputs["review"]["first"]["acting"]) == ["uncited_span"]      # the deterministic issue still acts
    # The failed review call was tried twice (llm.client.complete_structured); then one fix, one review.
    assert _events(fake_db) == ["archetype", "generate", "review", "review", "targeted_fix", "review"]
    # Nothing to reuse from a review that did not happen: every sentence is sent.
    second = outputs["review_second"]
    assert (second["outcome"], second["reviewed"], second["reused"], second["unreviewed"]) == ("clean", 3, 0, [])
    assert _review(result) == ("fixed", []) and outputs["review"]["unreviewed"] == []


def test_a_failed_first_review_does_not_hide_issues_the_second_review_finds(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], reviews=[NOT_A_TOOL_CALL, {"changes": {2: UNSUPPORTED}}], fixes=FIX_LINE_3)

    result = _run("B")

    assert _review(result) == ("issues_remain", [("not_in_sources", "That is most of the argument.")])


@pytest.mark.parametrize("failed_pass", [0, 1])
def test_a_returned_post_whose_own_review_failed_is_not_reviewed(claude, fake_db, seeded_kb, failed_pass):
    reviews = [{}, {}]
    reviews[failed_pass] = NOT_A_TOOL_CALL if failed_pass == 0 else {"replace": {3: "not a tool call"}}
    # First case: nothing acts, so the unreviewed first draft is returned. Second: the review of the fix fails.
    answer_pipeline(claude, [CLEAN] if failed_pass == 0 else [UNCITED], reviews=reviews, fixes=FIX_LINE_3)

    result = _run("B")

    assert result["review"]["outcome"] == "not_reviewed"
    assert _events(fake_db).count("targeted_fix") == failed_pass
    assert _outputs(fake_db)["review"]["unreviewed"]                  # the sentences nothing reviewed are named


def test_one_sentence_with_no_valid_record_makes_the_post_not_reviewed(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN], reviews=[{"changes": {1: MADE_UP}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert [i["reason"] for i in outputs["review_first"]["invalid"]] == ["evidence_not_in_source"]
    assert outputs["review"]["unreviewed"] == ["pgvector makes retrieval fast."]
    assert _review(result) == ("not_reviewed", []) and "fixes" not in outputs["review"]      # never clean


def test_a_sentence_with_no_valid_record_is_sent_again_and_never_reused(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], reviews=[{"changes": {1: MADE_UP}}], fixes=FIX_LINE_3)

    result = _run("B")

    second = _outputs(fake_db)["review_second"]
    assert (second["reused"], second["reviewed"], second["unreviewed"]) == (1, 2, [])    # sentences 1 and 3 were sent
    assert _review(result) == ("fixed", [])


# --- The full redraft -----------------------------------------------------------------

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


# --- The response and the trace -------------------------------------------------------

def test_the_response_lists_acting_issue_types_and_what_was_removed(claude, fake_db, seeded_kb, client, auth_headers,
                                                                  monkeypatch):
    monkeypatch.setenv("PIPELINE_VARIANT", "B")
    feeling = dict(content="feeling_or_reaction", stated_as="authors_view", presented_as="author_did_or_experienced")
    answer_pipeline(claude, [f"That part stings a little. [[V]]\n\n{UNCITED}"], fixes=fixes_reply({4: "Still none."}),
                    reviews=[{"changes": {1: feeling}, "rhythm": {2: {"sentence": 2, "why": RHYTHM_WHY}}}])

    body = client.post("/generate", json=REQUEST, headers=auth_headers(KB_USER)).json()

    assert body["review"] == {
        "outcome": "issues_remain",
        "issues": [{"type": "uncited_span", "sentence_text": "No marker on this line."}],
        "removed": [{"kind": "feeling_or_reaction", "text": "That part stings a little."}]}
    assert (body["status"], body["scored"], body["score"]) == ("ok", False, 0)
    assert "That part stings" not in body["post"]
    assert _types(_outputs(fake_db)["review"]["second"]["recorded"]) == ["ai_rhythm"]    # in the trace, never returned
    assert RHYTHM_WHY not in json.dumps(body)


def test_the_trace_records_both_passes_the_fixes_and_each_step(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], fixes=FIX_LINE_3)

    _run("B")

    outputs = _outputs(fake_db)
    record = outputs["review"]
    assert set(record) == {"first", "fixes", "targeted", "second", "removed", "remaining", "unreviewed", "outcome"}
    assert set(record["fixes"]) == {"code", "origin", "unplaced", "route"}
    [entry] = record["targeted"]["entries"]
    assert (entry["type"], entry["sentence"], entry["material"]) == ("uncited_span", 3, [["Text", "No marker on this line."]])
    assert record["targeted"]["answer"] == FIX_LINE_3
    assert (record["targeted"]["input_tokens"], record["targeted"]["output_tokens"]) == (10, 10)
    assert outputs["review_first"]["input_tokens"] == outputs["review_second"]["input_tokens"] == 10
    assert [t["step"] for t in outputs["step_timings"]] == [
        "structure", "draft", "strip", "finalise", "checks", "review_draft", "decide",
        "code_fix", "targeted_fix", "review_fixed", "outcome"]
    assert outputs["checks_final"] == {"issues": [], "counts": {}}       # the returned post's checks
    assert record["first"]["checks"]["counts"] == {"uncited_span": 1}


# --- Quality, and the other variants -----------------------------------------------------

def test_quality_draft_under_b_runs_as_c_does(claude, fake_db, seeded_kb):
    claude.queue('{"archetype": "general"}', enveloped(UNCITED))        # two calls and no more: an unqueued call fails

    result = _run("B", quality="draft")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate"]
    assert result["review"] is None and not {"review", "review_first", "review_second"} & set(outputs)
    assert outputs["checks_final"]["counts"] == {"uncited_span": 1}          # recorded, not acted on


def test_quality_polished_under_b_is_standard_b_with_no_scorer(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], fixes=FIX_LINE_3)

    result = _run("B", quality="polished")

    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix", "review"]
    assert (result["scored"], result["score"], result["review"]["outcome"]) == (False, 0, "fixed")


def test_variant_c_makes_no_review_call_and_no_fix(claude, fake_db, seeded_kb):
    claude.queue('{"archetype": "general"}', f"Sure.\n<post>\n{UNCITED}\n</post>")

    result = _run("C")

    assert _events(fake_db) == ["archetype", "generate"]
    assert result["review"] is None and result["post"] == _clean(UNCITED)    # C reads the same envelope
    assert not {"review", "review_first", "step_timings"} & set(_outputs(fake_db))


@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_draft_with_no_post_tag_is_still_a_post_and_the_trace_says_so(claude, fake_db, seeded_kb, variant):
    # The fallback, on purpose (one of the few tests that take it): the draft is used whole.
    claude.queue('{"archetype": "general"}', CLEAN)

    result = _run(variant, quality="draft")

    assert result["post"] == _clean(CLEAN)
    assert _outputs(fake_db)["draft_format"] == [{"draft": "draft", "kind": "post_tag_missing", "text": ""}]


def test_variant_a_returns_no_review(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    result = _run("A")

    assert result["review"] is None and result["post"] == "Final text."
