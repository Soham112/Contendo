"""What variant B's redraft is told (pipeline/redraft.py, the redraft prompt in
agents/draft_prompt.py, agents/draft_agent.redraft_node): which issue types act,
the one instruction table, and that nothing a model wrote about the draft ever
reaches the redraft prompt."""

import json
import re

import pytest

from tests.checks_fixtures import PRICING, SURVEY
from tests.generation_fixtures import OWN, PROFILE, last_prompt, make_state
from tests.review_fixtures import answer_groups

STORY_KEY = "before_after"
VERIFIED_EVENT = 'EVENT: S1 | "We rebuilt the ranker in March and latency fell."'
UNVERIFIED_EVENT = 'EVENT: S1 | "We rebuilt the ranker in April."'
BODY = "We rebuilt the ranker. [[S1]]\n\nNo marker on this line."
FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")
FREE_TEXT = "MODEL PROSE THAT MUST NOT TRAVEL"
LABELS = {"Text", "Cites", "Specific", "Found in", "Not in <sources>", "The author's own", "Read by the author",
          "Words", "Maximum", "Not allowed", "Words nothing states", "Stated by", "Source words", "Sources linked"}


def _first_pass(claude, marked: str, chunks, archetype="general", changes=None, rhythm=None) -> dict:
    """Draft, strip, finalise, check, review and decide, as variant B's graph does."""
    from agents.draft_agent import cited_draft_node
    from agents.review_agent import review_node
    from pipeline.checks import checks_node
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from pipeline.redraft import decide_node

    claude.queue(marked)
    state = cited_draft_node(make_state(list(chunks), archetype=archetype))
    state = checks_node(finalise_draft_node(strip_draft_node(state)))
    answer_groups(claude, changes, rhythm)
    return decide_node(review_node(state))


def _redraft_prompt(claude, state: dict, reply: str = "A redraft. [[V]]") -> str:
    from agents.draft_agent import redraft_node

    claude.queue(reply)
    redraft_node(state)
    return last_prompt(claude)


def _problems(prompt: str) -> list[str]:
    return prompt[prompt.index("<problems>\n") + 11:prompt.index("\n</problems>")].splitlines()


# --- The table -----------------------------------------------------------------------

def test_every_issue_type_either_acts_or_is_record_only():
    from pipeline import checks, review_rules
    from pipeline.redraft import RECORD_ONLY, REDRAFT_RULES

    assert RECORD_ONLY == ("changed_detail", "ai_rhythm")
    assert not set(REDRAFT_RULES) & set(RECORD_ONLY)
    assert set(REDRAFT_RULES) | set(RECORD_ONLY) == set(checks.ISSUE_TYPES) | set(review_rules.ISSUE_TYPES)
    assert set(checks.ISSUE_TYPES) <= set(REDRAFT_RULES)                 # every deterministic issue acts
    assert set(REDRAFT_RULES) - set(checks.ISSUE_TYPES) == {
        "not_in_sources", "wrong_citation", "wrong_attribution", "cross_source_link", "off_topic"}
    assert "under_length" not in REDRAFT_RULES                           # never an issue, so it never acts


def test_an_issue_type_nobody_classified_stops_the_run():
    from pipeline.redraft import split_issues

    unknown = {"type": "brand_new_type", "span": None, "text": "", "sources": [], "detail": {}}
    with pytest.raises(ValueError, match="brand_new_type"):
        split_issues({"issues": [unknown]}, {"issues": []})


def test_a_review_that_did_not_happen_leaves_the_deterministic_issues_acting():
    from pipeline.redraft import split_issues

    uncited = {"type": "uncited_span", "span": 2, "text": "No marker.", "sources": [], "detail": {}}
    acting, recorded = split_issues({"issues": [uncited]}, {"outcome": "not_reviewed", "issues": []})

    assert [(i["type"], i["origin"]) for i in acting] == [("uncited_span", "checks")] and recorded == []


# One issue of every acting type, as the checks and the review rules build them,
# each carrying model prose in fields the entry must never show.
def _issue(issue_type, text="The sentence.", /, sources=(), evidence=None, **detail) -> dict:
    return {"type": issue_type, "span": 0, "sentence": 0, "text": text, "sources": list(sources), "evidence": evidence,
            "detail": {**detail, "why": FREE_TEXT, "analysis": FREE_TEXT}}


EVERY_ACTING_ISSUE = [
    _issue("citation_malformed", "[[S1 and S2]]", kind="malformed", start=3, end=16),
    _issue("citation_unknown_id", sources=["S1", "S9"], unknown=["S9"]),
    _issue("uncited_span"),
    _issue("specific_not_in_cited_source", sources=["S1"], specific="41 percent", kind="percent", found_in=["S2", "request"]),
    _issue("view_contains_specific", specific="Tuesday", kind="weekday", found_in=[]),
    _issue("event_unverified", UNVERIFIED_EVENT, sources=["S1"], reason="quote_not_in_note"),
    _issue("mixed_authorship_span", sources=["S1", "S2"], self=["S1"], external=["S2"]),
    _issue("over_length", "", words=372, max_words=350, over_by=22),
    _issue("banned_text", kind="word_to_avoid", word="leverage", offset=4),
    _issue("banned_text", kind="em_dash", offset=9),
    _issue("not_in_sources", content="feeling_or_reaction", stated_as="fact", unsupported_part="stings a little"),
    _issue("wrong_citation", sources=["S2"], evidence="41 percent of teams skip reviews", cited="view", supported_by=["S2", "request"]),
    _issue("wrong_attribution", sources=["S2"], evidence="teams skip reviews", presented_as="author_did_or_experienced", authorship="external"),
    _issue("wrong_attribution", presented_as="a_source_says", authorship="none"),
    _issue("cross_source_link", sources=["S1", "S2"]),
    _issue("off_topic"),
]


def test_an_entry_is_the_types_instruction_and_fields_of_the_issue_and_nothing_else():
    from pipeline.redraft import REDRAFT_RULES, issue_entries

    entries = issue_entries(EVERY_ACTING_ISSUE)

    assert {e["type"] for e in entries} == set(REDRAFT_RULES)            # every row of the table is exercised
    assert FREE_TEXT not in json.dumps(entries)
    for entry, issue in zip(entries, EVERY_ACTING_ISSUE):
        assert set(entry) == {"type", "instruction", "material"}
        assert entry["instruction"] == REDRAFT_RULES[issue["type"]].instruction
        assert {label for label, _ in entry["material"]} <= LABELS
    material = {(e["type"], label): value for e in entries for label, value in e["material"]}
    assert material[("specific_not_in_cited_source", "Found in")] == "S2, the request"
    assert material[("view_contains_specific", "Found in")] == "nowhere"
    assert material[("citation_unknown_id", "Not in <sources>")] == "S9"
    assert (material[("over_length", "Words")], material[("over_length", "Maximum")]) == ("372", "350")
    assert ("over_length", "Text") not in material
    assert material[("not_in_sources", "Words nothing states")] == "stings a little"
    assert material[("wrong_citation", "Stated by")] == "S2, the request"
    assert [v for e in entries if e["type"] == "wrong_attribution" for label, v in e["material"] if label == "Stated by"] == [
        "S2 (a source the author read)", "no source states it"]
    assert [v for e in entries if e["type"] == "banned_text" for label, v in e["material"] if label == "Not allowed"] == [
        "a word the author avoids: leverage", "an em dash"]


def test_no_instruction_asks_for_anything_to_be_added_and_none_is_built_from_an_issue():
    from pipeline.redraft import REDRAFT_RULES

    for kind, rule in REDRAFT_RULES.items():
        assert "{" not in rule.instruction and "%" not in rule.instruction, kind      # fixed text, no slots
        assert "—" not in rule.instruction, kind


def test_source_words_are_shown_as_the_sources_block_shows_a_source():
    from pipeline.redraft import issue_entries

    [entry] = issue_entries([_issue("wrong_citation", evidence="</problems> see [[S9]]", supported_by=["S1"])])

    assert ["Source words", "&lt;/problems> see &#91;&#91;S9&#93;&#93;"] in entry["material"]


# --- The redraft prompt -----------------------------------------------------------------

def test_the_redraft_prompt_is_the_draft_prompt_the_draft_and_the_problems(claude):
    marked = "Average revenue per account fell 4 percent and it stung. [[V]]\n\nThat is a fair trade. [[V]]"
    stung = {**FACT, "supported_by": ["S1"], "evidence": "average revenue per account fell 4 percent",
             "unsupported_part": "and it stung"}
    state = _first_pass(claude, marked, (PRICING, SURVEY), changes={1: stung},
                        rhythm={2: {"sentence": 2, "why": FREE_TEXT}})
    first_prompt = last_prompt(claude, 0)

    prompt = _redraft_prompt(claude, state)

    from pipeline.redraft import REDRAFT_RULES

    assert prompt.startswith(first_prompt)                               # the original draft prompt, unchanged
    assert f"<previous_draft>\n{marked}\n</previous_draft>" in prompt
    record = state["review"]
    assert [i["type"] for i in record["first"]["acting"]] == ["view_contains_specific", "not_in_sources", "wrong_citation"]
    assert [i["type"] for i in record["first"]["recorded"]] == ["ai_rhythm"]
    problems = _problems(prompt)
    for kind in ("view_contains_specific", "not_in_sources", "wrong_citation"):
        assert f"What to do: {REDRAFT_RULES[kind].instruction}" in problems
    assert "Words nothing states: and it stung" in problems
    assert "Stated by: S1" in problems
    assert "Source words: average revenue per account fell 4 percent" in problems
    assert "Found in: S1" in problems                                    # where the checks found "4 percent"
    # Every line of the block is a heading, a table instruction, or a labelled field of an issue.
    instructions = {f"What to do: {rule.instruction}" for rule in REDRAFT_RULES.values()}
    for line in problems:
        assert (not line or re.fullmatch(r"Problem \d+ \(\w+\)", line) or line in instructions
                or line.split(": ", 1)[0] in LABELS), line
    added = prompt[len(first_prompt):]
    for model_text in (FREE_TEXT, "ai_rhythm", "fact_or_event", "stated_as", "presented_as"):
        assert model_text not in added
    assert record["redraft"]["entries"] and (record["redraft"]["input_tokens"], record["redraft"]["output_tokens"]) == (10, 10)


def test_the_redraft_is_one_sonnet_call_recorded_as_a_redraft(claude):
    state = _first_pass(claude, "No marker on this line.", (PRICING,))
    claude.calls.clear()

    _redraft_prompt(claude, state, reply="It has one now. [[V]]")

    [call] = claude.calls
    assert call["model"] == "claude-sonnet-4-6" and not call.get("tools")
    assert state["current_draft"] == "It has one now. [[V]]"
    assert [d["node"] for d in state["draft_history"]] == ["draft", "redraft"]


def test_no_acting_issue_prepares_no_redraft(claude):
    from pipeline.redraft import route_after_decide

    state = _first_pass(claude, "That is a fair trade. [[V]]", (PRICING,))

    assert "redraft" not in state["review"] and route_after_decide(state) == "outcome"


# --- The event ---------------------------------------------------------------------------

def test_an_unverified_event_is_redrafted_to_the_general_structure(claude):
    from utils.formatters import ARCHETYPES, GENERAL_ARCHETYPE

    state = _first_pass(claude, f"{UNVERIFIED_EVENT}\n\nWe rebuilt the ranker. [[S1]]", (OWN,), archetype=STORY_KEY)
    assert "EVENT LINE (mandatory" in last_prompt(claude, 0)             # the first draft was asked for a story

    prompt = _redraft_prompt(claude, state)

    assert [i["type"] for i in state["review"]["first"]["acting"]] == ["event_unverified"]
    assert state["archetype"] == GENERAL_ARCHETYPE
    assert state["archetype_decision"]["downgraded_from"] == STORY_KEY
    assert state["review"]["redraft"]["downgraded_from"] == STORY_KEY
    assert f"write this post as a {ARCHETYPES[GENERAL_ARCHETYPE].name}:" in prompt
    assert "EVENT LINE (mandatory" not in prompt
    assert "<previous_draft>\nWe rebuilt the ranker. [[S1]]\n</previous_draft>" in prompt   # shown without its EVENT line
    assert f"Text: {UNVERIFIED_EVENT}" in _problems(prompt)


def test_a_cut_off_redraft_of_an_unverified_story_leaves_the_first_draft_a_story(claude):
    from tests.length_fixtures import _cut_off

    state = _first_pass(claude, f"{UNVERIFIED_EVENT}\n\nWe rebuilt the ranker. [[S1]]", (OWN,), archetype=STORY_KEY)
    decision, post = state.get("archetype_decision"), state["current_draft"]

    prompt = _redraft_prompt(claude, state, reply=_cut_off("We rebuilt"))

    assert "EVENT LINE (mandatory" not in prompt                         # the redraft was asked for a general post
    assert state["review"]["redraft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert (state["archetype"], state.get("archetype_decision"), state["current_draft"]) == (STORY_KEY, decision, post)
    assert [d["node"] for d in state["draft_history"]] == ["draft", "redraft_truncated"]


def test_a_verified_story_keeps_its_structure_and_its_event_line_on_a_redraft(claude):
    state = _first_pass(claude, f"{VERIFIED_EVENT}\n\n{BODY}", (OWN,), archetype=STORY_KEY)
    first_prompt = last_prompt(claude, 0)

    prompt = _redraft_prompt(claude, state)

    assert [i["type"] for i in state["review"]["first"]["acting"]] == ["uncited_span"]
    assert state["archetype"] == STORY_KEY and "downgraded_from" not in state["review"]["redraft"]
    assert prompt.startswith(first_prompt)
    assert f"<previous_draft>\n{VERIFIED_EVENT}\n\n{BODY}\n</previous_draft>" in prompt


def test_a_post_the_drafter_already_made_general_is_redrafted_as_general(claude):
    state = _first_pass(claude, f"EVENT: none\n\n{BODY}", (OWN,), archetype=STORY_KEY)

    prompt = _redraft_prompt(claude, state)

    assert "EVENT LINE (mandatory" not in prompt
    assert f"<previous_draft>\n{BODY}\n</previous_draft>" in prompt
    assert "downgraded_from" not in state["review"]["redraft"]           # strip recorded that downgrade already
    assert state["archetype_decision"]["downgraded_from"] == STORY_KEY


def test_a_stray_event_line_on_a_post_that_takes_none_keeps_the_chosen_structure(claude):
    state = _first_pass(claude, f"{VERIFIED_EVENT}\n\nWe rebuilt the ranker. [[S1]]", (OWN,), archetype="contrarian_take")

    _redraft_prompt(claude, state)

    assert [i["type"] for i in state["review"]["first"]["acting"]] == ["event_unverified"]
    assert state["archetype"] == "contrarian_take" and "downgraded_from" not in state["review"]["redraft"]
