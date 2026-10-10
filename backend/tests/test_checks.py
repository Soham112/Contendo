"""Deterministic checks on a single-writer post (pipeline/checks.py): what each
one finds, and what it leaves alone. No check calls a model, and none changes
the post."""

import json

import pytest

from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import ARTICLE, OWN, PROFILE, make_state
from tests.length_fixtures import _outputs, _run
from tests.test_generation_trace import STANDARD_RUN, seeded_kb  # noqa: F401  (shared fixture)

# S1: the author's own note. S2: something the author read.
PRICING = {"memory_context": "work", "source_type": "note", "source_title": "Pricing test", "tags": "pricing",
           "text": ("Results: conversion improved from 13 to 16 percent; average revenue per account fell 4 percent; "
                    "shared logins rose. Early meetings were me presenting slides for an hour. "
                    "The rollout took three months.")}
SURVEY = {"memory_context": "learning", "source_type": "article", "source_title": "Review survey", "tags": "reviews",
          "text": "The survey found that 41 percent of teams skip reviews. Churn fell by a third at the firms that did not."}
STORY_KEY = "before_after"


def _lines(count: int) -> list[str]:
    """count one-sentence view lines of ten words each, with no digit in them
    (a number in a view span is itself an issue)."""
    return [" ".join(["Plain", *["word"] * 9]) + ". [[V]]" for _ in range(count)]


def _post(count: int) -> str:
    return "\n\n".join(_lines(count))


def _check(marked: str, chunks=(PRICING, SURVEY), archetype="general", **overrides) -> dict:
    """Strip, finalise and check a marked draft, as the graph does; returns checks_final."""
    from pipeline.checks import checks_node
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from utils.frames import build_sources_block

    chunks = list(chunks)
    state = make_state(chunks, archetype=archetype, current_draft=marked,
                       source_index=build_sources_block(chunks, PROFILE).index, **overrides)
    state = checks_node(finalise_draft_node(strip_draft_node(state)))
    assert state["checks_before_trim"] == state["checks_final"]
    return state["checks_final"]


def _of(result: dict, issue_type: str) -> list[dict]:
    return [issue for issue in result["issues"] if issue["type"] == issue_type]


def test_a_clean_post_has_no_issues_and_every_issue_has_the_same_shape():
    clean = _check("Average revenue per account fell 4 percent. [[S1]]\n\nThat is a trade worth knowing about. [[V]]")
    assert clean == {"issues": [], "counts": {}}

    messy = _check("A claim with no marker.\n\nConversion hit 99 percent. [[S1]]\n\nTwo is plenty. [[V]]")
    assert messy["counts"] == {"uncited_span": 1, "specific_not_in_cited_source": 1, "view_contains_specific": 1}
    for issue in messy["issues"]:
        assert set(issue) == {"type", "span", "text", "sources", "detail"}
        assert isinstance(issue["detail"], dict) and isinstance(issue["sources"], list)
    json.dumps(messy)                                             # the trace stores it as JSON


# --- 1. citation_malformed ---------------------------------------------------------

def test_malformed_markers_are_reported_with_their_kind():
    result = _check("One claim. [[S1 and S2]]\n\nAnother. [S1]\n\nA third one [[\n\n[[V]]")

    assert [(i["detail"]["kind"], i["text"]) for i in _of(result, "citation_malformed")] == [
        ("malformed", "[[S1 and S2]]"), ("single_brackets", "[S1]"), ("unbalanced", "[["), ("empty_span", "[[V]]")]
    assert all(i["span"] is None for i in _of(result, "citation_malformed"))


def test_well_formed_markers_and_ordinary_brackets_are_not_malformed():
    result = _check("See [the docs](https://example.com) for item [2]. [[V]]\n\nRevenue fell 4 percent. [[S1]]")

    assert _of(result, "citation_malformed") == []


def test_after_a_trim_only_markers_still_in_the_post_are_reported(claude):
    from agents.word_count_enforcer_agent import trim_node
    from pipeline.checks import checks_node, recheck_node
    from pipeline.finalise import finalise_draft_node, finalise_trimmed_node

    marked = "A bad one. [[S1 and S2]]\n\nA stray one. [S1]\n\n" + _post(12)
    state = make_state([OWN], archetype="general", current_draft=marked, source_index={},
                       length_target={"min_words": 0, "max_words": 120, "may_expand": False, "basis": "thin_sources"})
    state = checks_node(finalise_draft_node(state))
    claude.queue(json.dumps({"ranking": [5]}))
    state = recheck_node(finalise_trimmed_node(trim_node(state)))

    assert [i["detail"]["kind"] for i in _of(state["checks_before_trim"], "citation_malformed")] == ["malformed", "single_brackets"]
    assert [(i["detail"]["kind"], i["text"]) for i in _of(state["checks_final"], "citation_malformed")] == [("single_brackets", "[S1]")]


# --- 2. citation_unknown_id --------------------------------------------------------

def test_a_cited_id_that_is_not_a_source_of_this_run_is_reported():
    result = _check("Revenue fell 4 percent. [[S1]]\n\nSomething else happened. [[S9]]\n\nBoth agree. [[S2,S7]]")

    assert [(i["span"], i["sources"], i["detail"]) for i in _of(result, "citation_unknown_id")] == [
        (1, ["S9"], {"unknown": ["S9"]}), (2, ["S2", "S7"], {"unknown": ["S7"]})]


# --- 3. uncited_span ---------------------------------------------------------------

def test_prose_without_a_marker_is_reported_and_structure_is_not():
    result = _check("## A heading\n\nA claim with no marker.\n\n[DIAGRAM: the flow]\n\n```\ncode here\n```\n\n"
                    "Cited. [[S1]] Trailing claim.")

    assert [(i["span"], i["text"]) for i in _of(result, "uncited_span")] == [
        (0, "A claim with no marker."), (2, "Trailing claim.")]


# --- 4. specific_not_in_cited_source -----------------------------------------------

@pytest.mark.parametrize("sentence", [
    "Average revenue per account fell 4 percent.",          # the plan's regression case: must not be flagged
    "Revenue per account fell 4%.",
    "Conversion went from thirteen to sixteen percent.",
    "Conversion improved from 13 to 16 percent.",
    "The rollout took three months.",
    "It took 3 months to roll out.",
])
def test_a_specific_the_cited_source_states_passes_in_any_number_format(sentence):
    assert _of(_check(f"{sentence} [[S1]]"), "specific_not_in_cited_source") == []


def test_a_number_only_in_another_source_is_reported_and_that_source_is_named():
    result = _check("About 41 percent of teams skip reviews. [[S1]]")

    [issue] = _of(result, "specific_not_in_cited_source")
    assert (issue["span"], issue["sources"]) == (0, ["S1"])
    assert issue["detail"] == {"specific": "41 percent", "kind": "percent", "found_in": ["S2"]}


def test_a_number_in_no_source_is_reported_with_nowhere_to_find_it():
    [issue] = _of(_check("Conversion reached 99 percent. [[S1]]"), "specific_not_in_cited_source")

    assert issue["detail"] == {"specific": "99 percent", "kind": "percent", "found_in": []}


def test_citing_both_sources_accepts_what_either_states():
    result = _check("Revenue fell 4 percent while 41 percent of teams skip reviews. [[S1,S2]]")

    assert _of(result, "specific_not_in_cited_source") == []


def test_a_request_span_is_checked_against_the_topic_and_context():
    request = dict(topic="What 41 investor meetings taught me", context="We closed in 2019")

    assert _of(_check("It took 41 meetings and we closed in 2019. [[R]]", **request), "specific_not_in_cited_source") == []

    [issue] = _of(_check("It took 42 meetings. [[R]]", **request), "specific_not_in_cited_source")
    assert issue["detail"] == {"specific": "42", "kind": "number", "found_in": []}

    [issue] = _of(_check("Revenue fell 4 percent. [[R]]", **request), "specific_not_in_cited_source")
    assert issue["detail"]["found_in"] == ["S1"]                   # a source states it: cite the source instead


def test_a_specific_from_the_request_cited_to_a_source_names_the_request():
    [issue] = _of(_check("It took 57 meetings. [[S1]]", topic="What 57 investor meetings taught me"),
                  "specific_not_in_cited_source")

    assert issue["detail"]["found_in"] == ["request"]


def test_a_bare_number_matches_any_figure_of_that_value_in_the_cited_source():
    # Known limit, inherited from utils.specifics: only the value is compared, not what it counts.
    # "41 meetings" passes against a source that says "41 percent". What a number counts is for the review.
    assert _of(_check("We held 41 meetings. [[S2]]"), "specific_not_in_cited_source") == []


@pytest.mark.parametrize("sentence,specific", [
    ("Churn fell 33 percent at those firms. [[S2]]", "33 percent"),      # the source says "a third": not judged equal
    ("The rollout took 90 days. [[S1]]", "90 days"),                     # the source says "three months"
    ("The rollout took a quarter. [[S1]]", None),                        # no specific here to check
])
def test_nothing_that_needs_judging_is_treated_as_the_same_figure(sentence, specific):
    found = [i["detail"]["specific"] for i in _of(_check(sentence), "specific_not_in_cited_source")]

    assert found == ([specific] if specific else [])


def test_fractions_in_words_are_not_specifics_so_this_check_cannot_see_them():
    # Known limit: "a third" is not extracted, so a post saying it is not checked here.
    assert _of(_check("Revenue fell by a third. [[S1]]"), "specific_not_in_cited_source") == []


# --- 5. view_contains_specific -----------------------------------------------------

def test_any_specific_in_a_view_span_is_reported_even_when_a_source_states_it():
    result = _check("Losing 4 percent of revenue is a fair price. [[V]]\n\nTwo reviewers is plenty. [[V]]\n\n"
                    "It all went wrong last spring. [[V]]")

    assert [(i["span"], i["detail"]) for i in _of(result, "view_contains_specific")] == [
        (0, {"specific": "4 percent", "kind": "percent", "found_in": ["S1"]}),
        (1, {"specific": "Two", "kind": "number", "found_in": []}),
        (2, {"specific": "last spring", "kind": "time", "found_in": []}),
    ]
    assert _of(result, "specific_not_in_cited_source") == []


def test_a_view_with_no_specific_is_fine():
    assert _of(_check("That trade is worth making, and most teams never look. [[V]]"), "view_contains_specific") == []


# --- 6. event_unverified -----------------------------------------------------------

QUOTE = "Early meetings were me presenting slides for an hour."
BODY = "\n\nEarly on I presented slides for an hour. [[S1]]"


def _event(line: str, archetype=STORY_KEY, chunks=(PRICING, SURVEY)) -> list[dict]:
    return _of(_check(line + BODY if line else BODY.strip(), chunks, archetype=archetype), "event_unverified")


def test_an_event_quoted_word_for_word_from_the_authors_own_note_is_verified():
    assert _event(f'EVENT: S1 | "{QUOTE}"') == []
    assert _event('EVENT: S1 | "Results: conversion improved from 13 to 16 percent; average revenue per account '
                  'fell 4 percent; shared logins rose."') == []


@pytest.mark.parametrize("line,reason,sources", [
    ('EVENT: S1 | "My first board meetings were me presenting slides for an hour."', "event_quote_not_in_note", ["S1"]),
    ('EVENT: S1 | "Early meetings were me presenting slides"', "event_quote_not_sentence", ["S1"]),
    ('EVENT: S2 | "The survey found that 41 percent of teams skip reviews."', "source_not_own_experience", ["S2"]),
    ('EVENT: S9 | "Early meetings were me presenting slides for an hour."', "unknown_source", ["S9"]),
    ("EVENT: the board meetings", "event_line_malformed", []),
    ("", "event_line_missing", []),
])
def test_an_event_that_is_not_verified_says_why(line, reason, sources):
    [issue] = _event(line)

    assert issue["detail"]["reason"] == reason
    assert (issue["span"], issue["sources"], issue["text"]) == (None, sources, line)


def test_event_none_and_non_story_posts_have_no_event_to_verify():
    assert _event("EVENT: none") == []
    assert _event("", archetype="general") == []
    [issue] = _event(f'EVENT: S1 | "{QUOTE}"', archetype="general")
    assert issue["detail"]["reason"] == "event_line_unexpected"


def test_pipeline_a_and_the_checks_share_one_quote_check():
    import agents.archetype_agent as archetype_agent
    import pipeline.checks as checks
    import utils.sentences as sentences

    assert archetype_agent.event_quote_failure is checks.event_quote_failure is sentences.event_quote_failure
    assert archetype_agent.quote_is_in_note is sentences.quote_is_in_note


# --- 7. mixed_authorship_span ------------------------------------------------------

def test_a_span_citing_own_experience_and_an_external_source_is_reported():
    result = _check("Revenue fell 4 percent, and 41 percent of teams skip reviews. [[S1,S2]]")

    [issue] = _of(result, "mixed_authorship_span")
    assert (issue["span"], issue["sources"], issue["detail"]) == (0, ["S1", "S2"], {"self": ["S1"], "external": ["S2"]})


def test_spans_citing_sources_of_one_kind_are_not_mixed():
    both_own = _check("We rebuilt the ranker and revenue fell 4 percent. [[S1,S2]]", chunks=(PRICING, OWN))
    both_external = _check("Two things I read agree. [[S1,S2]]", chunks=(SURVEY, ARTICLE))
    separate = _check("Revenue fell 4 percent. [[S1]] And 41 percent of teams skip reviews. [[S2]]")

    for result in (both_own, both_external, separate):
        assert _of(result, "mixed_authorship_span") == []


# --- 8. over_length ----------------------------------------------------------------

def test_over_length_is_an_issue_and_under_length_is_not():
    over = _check(_post(36))                                       # 360 words against 250-350
    under = _check(_post(5))                                       # 50 words
    within = _check(_post(30))

    [issue] = _of(over, "over_length")
    assert (issue["span"], issue["detail"]) == (None, {"words": 360, "max_words": 350, "over_by": 10})
    assert under == {"issues": [], "counts": {}}
    assert within == {"issues": [], "counts": {}}


# --- 9. banned_text ----------------------------------------------------------------

def _banned(text: str, profile=None, first_post=False) -> list[dict]:
    from pipeline.checks import banned_text
    from utils.citations import strip_citations

    stripped = strip_citations(text)
    return banned_text(stripped.text, [s.as_dict() for s in stripped.spans], profile or {}, first_post)


def test_there_is_no_list_of_banned_phrases():
    import pipeline.checks as checks
    import utils.formatters as formatters

    # Wording that only sounds machine-written is for the review to judge, not for a lookup.
    for text in ("In today's market, speed wins. [[V]]", "A transformative, game-changing quarter. [[V]]",
                 "It's important to note that speed wins. [[V]]"):
        assert _banned(text) == []
    assert not [name for name in vars(formatters) if "BANNED" in name]
    assert not [name for name in vars(checks) if "BANNED" in name or "PHRASE" in name]


def test_the_profiles_words_to_avoid_are_reported_as_whole_words():
    profile = {"words_to_avoid": ["leverage", "10x", "north star", ""]}

    found = _banned("We leverage the data. [[V]]\n\nA 10x gain, our North Star. [[V]]\n\nWe leveraged nothing. [[V]]", profile)

    assert [(i["span"], i["detail"]["kind"], i["detail"]["word"]) for i in found] == [
        (0, "word_to_avoid", "leverage"), (1, "word_to_avoid", "10x"), (1, "word_to_avoid", "north star")]


@pytest.mark.parametrize("text", [
    "In today's market, speed wins. [[V]]",
    "IN TODAY’S market, speed wins. [[V]]",                      # any case, curly apostrophe
    "Speed wins in today's market. [[V]]",
])
def test_a_word_to_avoid_matches_in_any_case_and_with_either_apostrophe(text):
    [issue] = _banned(text, {"words_to_avoid": ["In today's"]})

    assert (issue["span"], issue["detail"]["kind"], issue["detail"]["word"]) == (0, "word_to_avoid", "In today's")


@pytest.mark.parametrize("text", [
    "The maintoday's log was empty. [[V]]",
    "Remaintoday is not a word. [[V]]",
    "Today's market rewards speed. [[V]]",
    "We leveraged nothing and were delighted. [[V]]",
])
def test_words_to_avoid_match_whole_words_only(text):
    assert _banned(text, {"words_to_avoid": ["In today's", "leverage", "delight"]}) == []


def test_a_profile_with_no_words_to_avoid_bans_no_words():
    assert _banned("We leverage game-changing synergy. [[V]]", {}) == []
    assert _banned("We leverage game-changing synergy. [[V]]", {"words_to_avoid": []}) == []


def test_an_em_dash_in_prose_is_reported_and_one_in_code_or_a_quoted_literal_is_not():
    found = _banned('It was fast — really fast. [[V]]\n\n```\na — b\n```\n\nShe wrote "wait — what" and left. [[V]]\n\nInline `x — y` too. [[V]]')

    assert [(i["span"], i["detail"]["kind"]) for i in found] == [(0, "em_dash")]


def test_a_finalised_post_has_no_em_dash_issue_because_finalise_removed_it():
    assert _of(_check("It was fast — really fast. [[V]]"), "banned_text") == []


def test_a_placeholder_is_banned_only_in_a_first_post():
    text = "The flow is simple. [[V]]\n\n[DIAGRAM: three boxes in a row]\n\n[IMAGE: the alert]"

    assert _banned(text, first_post=False) == []
    assert [(i["span"], i["text"], i["detail"]["kind"]) for i in _banned(text, first_post=True)] == [
        (None, "[DIAGRAM: three boxes in a row]", "placeholder_in_first_post"),
        (None, "[IMAGE: the alert]", "placeholder_in_first_post")]


def test_a_word_to_avoid_in_a_heading_is_reported_without_a_span():
    [issue] = _banned("## A year of synergy\n\nIt was fine. [[V]]", {"words_to_avoid": ["synergy"]})

    assert (issue["span"], issue["text"]) == (None, "synergy")


# --- Through run_pipeline --------------------------------------------------------

@pytest.mark.parametrize("variant", ["B", "C"])
def test_checks_are_recorded_and_add_no_call_and_change_no_post(claude, fake_db, seeded_kb, variant):
    marked = "\n\n".join([*_lines(28), "Latency fell 37 percent on a Tuesday. [[S1]]", "No marker on this line."])
    claude.queue(ARCHETYPE_GENERAL, marked)

    result = _run(variant)

    outputs = _outputs(fake_db)
    assert len(claude.calls) == 2                                  # structure and draft: the checks call no model
    assert outputs["checks_final"] == outputs["checks_before_trim"]
    assert outputs["checks_final"]["counts"] == {"uncited_span": 1, "specific_not_in_cited_source": 2}
    assert [i["detail"]["specific"] for i in _of(outputs["checks_final"], "specific_not_in_cited_source")] == ["37 percent", "Tuesday"]
    assert "Latency fell 37 percent on a Tuesday." in result["post"] and "No marker on this line." in result["post"]
    assert result["status"] == "ok"


@pytest.mark.parametrize("variant", ["B", "C"])
def test_checks_run_again_on_the_trimmed_post(claude, fake_db, seeded_kb, variant):
    claude.queue(ARCHETYPE_GENERAL, _post(36), json.dumps({"ranking": [10]}))      # 360 words, trimmed to 350

    _run(variant)

    outputs = _outputs(fake_db)
    assert len(claude.calls) == 3                                  # structure, draft, trim
    assert outputs["checks_before_trim"]["counts"] == {"over_length": 1}
    assert outputs["checks_final"] == {"issues": [], "counts": {}}


def test_pipeline_a_runs_no_checks(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    _run("A")

    assert not {"checks_before_trim", "checks_final"} & set(_outputs(fake_db))
