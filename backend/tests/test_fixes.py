"""Variant B's fixes to a reviewed draft (pipeline/fixes.py), through
run_pipeline with the fake model: what code fixes with no model call, the
targeted fix that can change flagged sentences only, and the record of what was
taken out. Routing between the paths is in test_pipeline_b.py."""

import json

import pytest

from tests.length_fixtures import _clean, _cut_off, _outputs, _run
from tests.review_fixtures import answer_pipeline, assigned, fixes_reply
from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)

SOURCED = "pgvector makes retrieval fast. [[S1]]"
VIEW = "That is most of the argument. [[V]]"
CLEAN = f"{SOURCED}\n\n{VIEW}"
UNCITED = f"{CLEAN}\n\nNo marker on this line."
MARKED_NOW = f"{CLEAN}\n\nThe line has a marker now. [[V]]"
FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")
FEELING = dict(content="feeling_or_reaction", stated_as="authors_view", presented_as="author_did_or_experienced")
STATED_BY_S1 = {**FACT, "supported_by": ["S1"], "evidence": "pgvector makes retrieval fast"}
NO_REMAINING = {"outcome": "fixed", "issues": []}


def _events(fake_db) -> list[str]:
    [trace] = fake_db.tables["generation_traces"]
    return [call["event_type"] for call in trace["llm_calls"]]


def _review(result: dict) -> dict:
    return {key: result["review"][key] for key in ("outcome", "issues")}


# --- Fixes made in code ---------------------------------------------------------------

def test_a_sentence_nothing_states_is_deleted_by_code_with_no_model_call(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN], reviews=[{"changes": {2: FEELING}}])

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert _events(fake_db) == ["archetype", "generate", "review"]          # no fix call, no second review call
    assert result["post"] == "pgvector makes retrieval fast."
    assert record["fixes"]["code"] == [{"type": "sentence_deleted", "issue": "not_in_sources", "sentence": 1,
                                        "before": VIEW, "after": None}]
    assert (record["fixes"]["route"], record["fixes"]["origin"]) == ("none", [0])
    assert _review(result) == NO_REMAINING
    assert result["review"]["removed"] == [{"kind": "feeling_or_reaction", "text": "That is most of the argument."}]
    assert record["removed"] == [{"kind": "feeling_or_reaction", "text": "That is most of the argument.",
                                  "how": "deleted", "by": "code"}]
    second = _outputs(fake_db)["review_second"]
    assert (second["reused"], second["reviewed"], second["groups"]) == (1, 0, 0)


@pytest.mark.parametrize("supported_by,evidence,marker,basis", [
    (["S1"], "pgvector makes retrieval fast", "[[S1]]", "sources"),
    (["request"], "pgvector retrieval", "[[R]]", "request"),
    (["S1", "request"], "pgvector makes retrieval fast", "[[S1]]", "sources"),
])
def test_a_wrong_marker_is_replaced_by_code_and_the_words_do_not_change(claude, fake_db, seeded_kb, supported_by,
                                                                        evidence, marker, basis):
    draft = f"pgvector makes retrieval fast. [[V]]\n\n{VIEW}"
    answer_pipeline(claude, [draft], reviews=[{"changes": {1: {**FACT, "supported_by": supported_by, "evidence": evidence}}}])

    result = _run("B")

    outputs = _outputs(fake_db)
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert result["post"] == _clean(draft)                                   # byte for byte
    assert outputs["review"]["fixes"]["code"] == [{
        "type": "marker_replaced", "issue": "wrong_citation", "sentence": 0,
        "before": "pgvector makes retrieval fast. [[V]]", "after": f"pgvector makes retrieval fast. {marker}"}]
    assert (outputs["citations"][0]["basis"], outputs["citations"][1]["basis"]) == (basis, "view")
    assert outputs["review_second"]["reused"] == 2                            # a marker alone changed: the record is kept
    assert _review(result) == NO_REMAINING and result["review"]["removed"] == []


def test_an_uncited_sentence_the_review_found_a_source_for_gets_its_marker_from_code(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [f"pgvector makes retrieval fast.\n\n{VIEW}"], reviews=[{"changes": {1: STATED_BY_S1}}])

    result = _run("B")

    first = _outputs(fake_db)["review"]["first"]
    assert sorted(i["type"] for i in first["acting"]) == ["uncited_span", "wrong_citation"]
    assert _events(fake_db) == ["archetype", "generate", "review"] and _review(result) == NO_REMAINING
    assert _outputs(fake_db)["citations"][0]["sources"] == ["S1"]


# --- The targeted fix -------------------------------------------------------------------

def test_a_targeted_fix_replaces_the_flagged_sentence_and_nothing_else(claude, fake_db, seeded_kb):
    prompts = answer_pipeline(claude, [UNCITED], fixes=fixes_reply({3: "The line has a marker now. [[V]]"}))

    result = _run("B")

    outputs = _outputs(fake_db)
    record = outputs["review"]
    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix", "review"]
    assert result["post"] == _clean(MARKED_NOW)
    assert result["post"].startswith(_clean(CLEAN))                          # the unflagged sentences, byte for byte
    assert record["fixes"]["route"] == "targeted" and record["targeted"]["flagged"] == [3]
    assert record["targeted"]["applied"] == [{"sentence": 3, "before": "No marker on this line.",
                                              "after": "The line has a marker now. [[V]]"}]
    assert record["targeted"]["invalid"] == [] and "redraft" not in record
    assert [d["node"] for d in outputs["draft_history"]] == ["draft", "targeted_fix"]
    assert _review(result) == NO_REMAINING
    # The fix prompt: the draft prompt, the numbered sentences with their markers, the problem and its sentence.
    assert prompts[1].startswith(prompts[0])
    assert ("<post_sentences>\n1. pgvector makes retrieval fast. [[S1]]\n2. That is most of the argument. [[V]]\n"
            "3. No marker on this line.\n</post_sentences>") in prompts[1]
    assert "Problem 1 (uncited_span), sentence 3\nWhat to do: " in prompts[1]


def test_the_second_review_sends_only_the_replaced_sentences(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], fixes=fixes_reply({3: "It has one. [[V]] So does this. [[S1]]"}))

    _run("B")

    outputs = _outputs(fake_db)
    last_review = [c for c in claude.calls if (c.get("tool_choice") or {}).get("name") == "record_review"][-1]
    assert assigned(last_review) == [3, 4]                                   # the two sentences of the replacement
    assert (outputs["review_second"]["reused"], outputs["review_second"]["reviewed"]) == (2, 2)
    assert outputs["review"]["fixes"]["origin"] == [0, 1, None, None]


def test_a_targeted_fix_may_leave_the_sentence_out(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [UNCITED], fixes=fixes_reply(delete=[3]))

    result = _run("B")

    assert result["post"] == _clean(CLEAN) and _review(result) == NO_REMAINING
    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix"]    # nothing new to review
    assert _outputs(fake_db)["review"]["targeted"]["applied"] == [
        {"sentence": 3, "before": "No marker on this line.", "after": None}]
    assert result["review"]["removed"] == [{"kind": "opinion", "text": "No marker on this line."}]


UNCITED_REMAINS = {"outcome": "issues_remain", "issues": [{"type": "uncited_span", "sentence_text": "No marker on this line."}]}


@pytest.mark.parametrize("answer,reasons", [
    (fixes_reply({1: "pgvector is slow. [[V]]", 3: "It has one. [[V]]"}).replace("</fixes>", '<fix sentence="3">Again. [[V]]</fix></fixes>'),
     ["not_flagged", "repeated"]),
    (fixes_reply({3: "Still no marker."}), ["uncited_text"]),
    (fixes_reply({3: "A bad marker. [[S1 and S2]]"}), ["marker_failure: ['malformed']"]),
    (fixes_reply({3: "   "}), ["empty"]),
    (fixes_reply({2: "Something else. [[V]]"}), ["not_flagged", "missing"]),
    ("I fixed sentence 3 for you.", ["missing"]),
    (_cut_off('<fixes><fix sentence="3">It has'), ["missing"]),
])
def test_an_invalid_fix_changes_nothing_and_its_issue_remains(claude, fake_db, seeded_kb, answer, reasons):
    answer_pipeline(claude, [UNCITED], fixes=answer)

    result = _run("B")

    outputs = _outputs(fake_db)
    assert result["post"] == _clean(UNCITED)                                 # no sentence changed, flagged or not
    assert [item["reason"] for item in outputs["review"]["targeted"]["invalid"]] == reasons
    assert outputs["review"]["targeted"]["applied"] == [] and _review(result) == UNCITED_REMAINS
    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix"]
    assert [d["node"] for d in outputs["draft_history"]] == ["draft"]


def test_a_valid_fix_is_applied_beside_an_invalid_one(claude, fake_db, seeded_kb):
    draft = f"{UNCITED}\n\nAnother line without one."
    answer_pipeline(claude, [draft], fixes=fixes_reply({3: "It has one now. [[V]]", 4: "This one does not."}))

    result = _run("B")

    assert result["post"] == _clean(f"{CLEAN}\n\nIt has one now. [[V]]\n\nAnother line without one.")
    assert result["review"]["issues"] == [{"type": "uncited_span", "sentence_text": "Another line without one."}]


def test_words_nothing_states_are_trimmed_by_the_targeted_fix_and_recorded_by_kind(claude, fake_db, seeded_kb):
    added = {**STATED_BY_S1, "unsupported_part": "and cheap"}
    prompts = answer_pipeline(claude, [f"pgvector makes retrieval fast and cheap. [[S1]]\n\n{VIEW}"],
                              reviews=[{"changes": {1: added}}], fixes=fixes_reply({1: SOURCED}))

    result = _run("B")

    assert result["post"] == _clean(CLEAN) and _review(result) == NO_REMAINING
    assert "Problem 1 (not_in_sources), sentence 1" in prompts[1] and "Words nothing states: and cheap" in prompts[1]
    assert result["review"]["removed"] == [{"kind": "fact_or_event", "text": "and cheap"}]
    assert _outputs(fake_db)["review"]["removed"] == [
        {"kind": "fact_or_event", "text": "and cheap", "how": "trimmed", "by": "model"}]


def test_code_fixes_come_first_and_the_targeted_fix_sees_the_post_after_them(claude, fake_db, seeded_kb):
    draft = f"Everyone felt relieved. [[V]]\n\n{UNCITED}"
    prompts = answer_pipeline(claude, [draft], reviews=[{"changes": {1: FEELING}}],
                              fixes=fixes_reply({3: "The line has a marker now. [[V]]"}))

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert [fix["type"] for fix in record["fixes"]["code"]] == ["sentence_deleted"]
    assert "1. pgvector makes retrieval fast. [[S1]]" in prompts[1] and "Everyone felt relieved" not in prompts[1].split("FIXES:")[1]
    assert record["targeted"]["flagged"] == [3]                              # the sentence after the deletion is not flagged
    assert result["post"] == _clean(MARKED_NOW) and _review(result) == NO_REMAINING
    assert [(r["how"], r["by"], r["kind"]) for r in record["removed"]] == [("deleted", "code", "feeling_or_reaction")]


# --- A whole sentence named as the unsupported part ------------------------------------

@pytest.mark.parametrize("part", [
    "There's a framework that tries to stop that.",         # the 6c live run on pm-09
    "there's a framework  that tries to stop that",        # case, spacing, the full stop
    "There's a framework that tries to stop that",          # no full stop
])
def test_an_unsupported_part_that_is_the_whole_sentence_is_deleted_by_code(claude, fake_db, seeded_kb, part):
    whole = dict(content="other", stated_as="fact", presented_as="neutral", unsupported_part=part)
    answer_pipeline(claude, [f"{CLEAN}\n\nThere's a framework that tries to stop that. [[V]]"],
                    reviews=[{"changes": {3: whole}}])

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert _events(fake_db) == ["archetype", "generate", "review"]          # no model call
    assert [(fix["type"], fix["sentence"]) for fix in record["fixes"]["code"]] == [("sentence_deleted", 2)]
    assert result["post"] == _clean(CLEAN) and _review(result) == NO_REMAINING
    assert result["review"]["removed"] == [{"kind": "other", "text": "There's a framework that tries to stop that."}]


def test_an_unsupported_part_that_is_only_part_of_the_sentence_is_not_deleted_by_code(claude, fake_db, seeded_kb):
    part = dict(content="other", stated_as="fact", presented_as="neutral", unsupported_part="a framework that tries")
    answer_pipeline(claude, [f"{CLEAN}\n\nThere's a framework that tries to stop that. [[V]]"],
                    reviews=[{"changes": {3: part}}], fixes=fixes_reply(delete=[3]))

    _run("B")

    record = _outputs(fake_db)["review"]
    assert record["fixes"]["code"] == [] and record["targeted"]["flagged"] == [3]


# --- After a deletion; and a fix that changes nothing --------------------------------------

EXPERIMENTS = "We kept running growth experiments on top of that. [[V]]"
ORPHAN = "Which, in hindsight, is a bit like mopping the floor while the tap is still running. [[V]]"


def test_the_sentence_after_a_code_deletion_is_left_as_it_is_and_no_model_is_asked(claude, fake_db, seeded_kb):
    # The 6c live run on pm-01, in small. Asking the drafter to repair such neighbours was tried in 6d and
    # removed: it rewrote sentences that needed nothing. An orphan like this one is accepted.
    answer_pipeline(claude, [f"{SOURCED}\n\n{EXPERIMENTS} {ORPHAN}\n\n{VIEW}"], reviews=[{"changes": {2: dict(FACT)}}])

    result = _run("B")

    record = _outputs(fake_db)["review"]
    assert _events(fake_db) == ["archetype", "generate", "review"]
    assert record["fixes"]["route"] == "none" and "targeted" not in record and "repairs" not in record["fixes"]
    assert result["post"] == _clean(f"{SOURCED}\n\n{ORPHAN}\n\n{VIEW}") and _review(result) == NO_REMAINING


def test_a_replacement_identical_to_the_sentence_counts_as_unchanged(claude, fake_db, seeded_kb):
    draft = f"pgvector makes retrieval fast and cheap. [[S1]]\n\n{VIEW}"
    added = {**STATED_BY_S1, "unsupported_part": "and cheap"}
    answer_pipeline(claude, [draft], reviews=[{"changes": {1: added}}],
                    fixes=fixes_reply({1: "pgvector makes  retrieval fast and cheap. [[S1]]"}))      # spacing only

    result = _run("B")

    outputs = _outputs(fake_db)
    targeted = outputs["review"]["targeted"]
    assert (targeted["unchanged"], targeted["applied"], targeted["invalid"]) == ([1], [], [])
    assert result["post"] == _clean(draft) and [d["node"] for d in outputs["draft_history"]] == ["draft"]
    # Nothing new to review: the sentence keeps its record, and so its issue.
    assert _events(fake_db) == ["archetype", "generate", "review", "targeted_fix"]
    assert outputs["review_second"]["reviewed"] == 0 and outputs["review"]["fixes"]["origin"] == [0, 1]
    assert _review(result) == {"outcome": "issues_remain", "issues": [
        {"type": "not_in_sources", "sentence_text": "pgvector makes retrieval fast and cheap."}]}


def test_the_fix_prompt_carries_no_model_prose(claude, fake_db, seeded_kb):
    why = "Reads like a slogan."
    prompts = answer_pipeline(claude, [UNCITED], reviews=[{"rhythm": {1: {"sentence": 1, "why": why}}}],
                              fixes=fixes_reply(delete=[3]))

    _run("B")

    added = prompts[1][len(prompts[0]):]
    for model_text in (why, "ai_rhythm", "authors_view", "stated_as"):
        assert model_text not in added
    assert json.dumps(_outputs(fake_db)["review"]["targeted"]["entries"]).count("uncited_span") == 1
