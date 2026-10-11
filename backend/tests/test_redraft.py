"""What a model is told about a reviewed draft's problems (pipeline/redraft.py,
agents/redraft_prompt.py) and the one full redraft (agents/draft_agent.redraft_node):
which issue types act and how, the one instruction table, the routing rule, and
that nothing a model wrote about the draft ever reaches a fix or redraft prompt."""

import json
import re

import pytest

from tests.checks_fixtures import PRICING, SURVEY
from tests.generation_fixtures import OWN, last_prompt, make_state
from tests.length_fixtures import _cut_off
from tests.review_fixtures import answer_groups, enveloped

STORY_KEY = "before_after"
VERIFIED = 'S1 | "We rebuilt the ranker in March and latency fell."'
UNVERIFIED = 'S1 | "We rebuilt the ranker in April."'
BODY = "We rebuilt the ranker. [[S1]]\n\nNo marker on this line."
FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")
FREE_TEXT = "MODEL PROSE THAT MUST NOT TRAVEL"
LABELS = {"Text", "Cites", "Specific", "Found in", "Not in <sources>", "The author's own", "Read by the author",
          "Words", "Maximum", "Not allowed", "Words nothing states", "Stated by", "Source words", "Sources linked"}
STORY_OUTPUT = "<event>{event}</event>\n<post>\n{post}\n</post>"


def _first_pass(claude, written: str, chunks, archetype="general", changes=None, rhythm=None) -> dict:
    """Draft, strip, finalise, check, review, decide and fix in code, as variant B's graph does."""
    from agents.draft_agent import cited_draft_node
    from agents.review_agent import review_node
    from pipeline.checks import checks_node
    from pipeline.finalise import finalise_draft_node, strip_draft_node
    from pipeline.fixes import code_fix_node
    from pipeline.redraft import decide_node

    claude.queue(enveloped(written))
    state = cited_draft_node(make_state(list(chunks), archetype=archetype))
    state = checks_node(finalise_draft_node(strip_draft_node(state)))
    answer_groups(claude, changes, rhythm)
    return code_fix_node(decide_node(review_node(state)))


def _redraft_prompt(claude, state: dict, reply="<post>\nA redraft. [[V]]\n</post>") -> str:
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
    # Every row is an issue type: there is no row for anything else (the after_deletion
    # repair step of 6d was removed on 2026-10-10; see the plan, section 6).
    assert set(REDRAFT_RULES) | set(RECORD_ONLY) == set(checks.ISSUE_TYPES) | set(review_rules.ISSUE_TYPES)
    assert set(checks.ISSUE_TYPES) <= set(REDRAFT_RULES)                 # every deterministic issue acts
    assert set(REDRAFT_RULES) - set(checks.ISSUE_TYPES) == {
        "not_in_sources", "wrong_citation", "wrong_attribution", "cross_source_link", "off_topic"}
    assert "under_length" not in REDRAFT_RULES                           # never an issue, so it never acts


def test_only_the_event_and_the_length_are_problems_with_the_whole_post():
    from pipeline.redraft import REDRAFT_RULES

    assert {kind for kind, rule in REDRAFT_RULES.items() if rule.scope == "post"} == {"event_unverified", "over_length"}
    # wrong_citation is always fixed in code, so there is nothing to tell a model about it.
    assert [kind for kind, rule in REDRAFT_RULES.items() if rule.instruction is None] == ["wrong_citation"]


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


# --- The routing rule ---------------------------------------------------------------------

def _left(kind: str, at) -> dict:
    return {"type": kind, "at": at}


@pytest.mark.parametrize("remaining,route", [
    ([], "none"),
    ([_left("banned_text", None)], "none"),                              # about no one sentence: nothing can fix it
    ([_left("uncited_span", 2)], "targeted"),
    ([_left("not_in_sources", 0), _left("off_topic", 4), _left("banned_text", None)], "targeted"),
    ([_left("over_length", None)], "full"),
    ([_left("event_unverified", None)], "full"),
    ([_left("uncited_span", 2), _left("over_length", None)], "full"),    # never both: the redraft takes them all
    ([_left("event_unverified", None), _left("wrong_attribution", 1)], "full"),
])
def test_the_routing_rule(remaining, route):
    from pipeline.fixes import choose_route

    assert choose_route(remaining) == route


# One issue of every type a model is told about, as the checks and the review rules
# build them, each carrying model prose in fields the entry must never show.
def _issue(issue_type, text="The sentence.", /, sources=(), evidence=None, **detail) -> dict:
    return {"type": issue_type, "span": 0, "sentence": 0, "at": 0, "text": text, "sources": list(sources),
            "evidence": evidence, "detail": {**detail, "why": FREE_TEXT, "analysis": FREE_TEXT}}


EVERY_ISSUE_A_MODEL_SEES = [
    _issue("citation_malformed", "[[S1 and S2]]", kind="malformed", start=3, end=16),
    _issue("citation_unknown_id", sources=["S1", "S9"], unknown=["S9"]),
    _issue("uncited_span"),
    _issue("specific_not_in_cited_source", sources=["S1"], specific="41 percent", kind="percent", found_in=["S2", "request"]),
    _issue("view_contains_specific", specific="Tuesday", kind="weekday", found_in=[]),
    _issue("event_unverified", UNVERIFIED, sources=["S1"], reason="quote_not_in_note"),
    _issue("mixed_authorship_span", sources=["S1", "S2"], self=["S1"], external=["S2"]),
    _issue("over_length", "", words=372, max_words=350, over_by=22),
    _issue("banned_text", kind="word_to_avoid", word="leverage", offset=4),
    _issue("banned_text", kind="em_dash", offset=9),
    _issue("not_in_sources", content="feeling_or_reaction", stated_as="fact", unsupported_part="stings a little"),
    _issue("wrong_attribution", sources=["S2"], evidence="teams skip reviews", presented_as="author_did_or_experienced", authorship="external"),
    _issue("wrong_attribution", presented_as="a_source_says", authorship="none"),
    _issue("cross_source_link", sources=["S1", "S2"]),
    _issue("off_topic"),
]


def test_an_entry_is_the_types_instruction_and_fields_of_the_issue_and_nothing_else():
    from pipeline.redraft import REDRAFT_RULES, issue_entries

    entries = issue_entries(EVERY_ISSUE_A_MODEL_SEES)

    assert {e["type"] for e in entries} == set(REDRAFT_RULES) - {"wrong_citation"}     # every row with an instruction
    assert FREE_TEXT not in json.dumps(entries)
    for entry, issue in zip(entries, EVERY_ISSUE_A_MODEL_SEES):
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
    assert [v for e in entries if e["type"] == "wrong_attribution" for label, v in e["material"] if label == "Stated by"] == [
        "S2 (a source the author read)", "no source states it"]
    assert [v for e in entries if e["type"] == "banned_text" for label, v in e["material"] if label == "Not allowed"] == [
        "a word the author avoids: leverage", "an em dash"]


def test_a_numbered_entry_names_its_sentence_and_a_code_fixed_type_has_no_entry():
    from pipeline.redraft import issue_entries

    [entry] = issue_entries([{**_issue("off_topic"), "at": 6}], numbered=True)
    assert entry["sentence"] == 7

    with pytest.raises(ValueError, match="wrong_citation"):
        issue_entries([_issue("wrong_citation", supported_by=["S1"])])


def test_every_instruction_is_fixed_text():
    from pipeline.redraft import REDRAFT_RULES

    for kind, rule in REDRAFT_RULES.items():
        if rule.instruction is not None:
            assert "{" not in rule.instruction and "%" not in rule.instruction and "—" not in rule.instruction, kind
            assert "EVENT line" not in rule.instruction, kind              # the convention the envelope replaced


def test_source_words_are_shown_as_the_sources_block_shows_a_source():
    from pipeline.redraft import issue_entries

    [entry] = issue_entries([_issue("wrong_attribution", sources=["S2"], evidence="</problems> see [[S9]]", authorship="external")])

    assert ["Source words", "&lt;/problems> see &#91;&#91;S9&#93;&#93;"] in entry["material"]


def test_both_prompts_list_problems_as_headings_table_instructions_and_labelled_fields_only():
    from agents.redraft_prompt import build_fix_prompt, build_redraft_prompt
    from pipeline.redraft import REDRAFT_RULES, issue_entries
    from utils.citations import strip_citations

    sentences = strip_citations("The sentence. [[V]]").spans
    instructions = {f"What to do: {rule.instruction}" for rule in REDRAFT_RULES.values()}
    for prompt, heading in [
        (build_fix_prompt("DRAFT PROMPT", sentences, issue_entries(EVERY_ISSUE_A_MODEL_SEES, numbered=True)),
         r"Problem \d+ \(\w+\), sentence 1"),
        (build_redraft_prompt("DRAFT PROMPT", "The sentence. [[V]]", issue_entries(EVERY_ISSUE_A_MODEL_SEES)),
         r"Problem \d+ \(\w+\)"),
    ]:
        assert prompt.startswith("DRAFT PROMPT\n\n") and FREE_TEXT not in prompt
        for line in _problems(prompt):
            assert (not line or re.fullmatch(heading, line) or line in instructions
                    or line.split(": ", 1)[0] in LABELS), line


# --- The full redraft -----------------------------------------------------------------------

def test_an_unverified_event_is_redrafted_whole_to_the_general_structure(claude):
    from utils.formatters import ARCHETYPES, GENERAL_ARCHETYPE

    state = _first_pass(claude, STORY_OUTPUT.format(event=UNVERIFIED, post=BODY), (OWN,), archetype=STORY_KEY)
    first_prompt = last_prompt(claude, 0)
    assert "EVENT (mandatory" in first_prompt                            # the first draft was asked for a story
    record = state["review"]
    assert record["fixes"]["route"] == "full" and "targeted" not in record
    assert state["archetype"] == STORY_KEY                               # not downgraded until the redraft is written

    prompt = _redraft_prompt(claude, state)

    assert [e["type"] for e in record["redraft"]["entries"]] == ["uncited_span", "event_unverified"]
    assert state["archetype"] == GENERAL_ARCHETYPE
    assert state["archetype_decision"]["downgraded_from"] == record["redraft"]["downgraded_from"] == STORY_KEY
    assert f"write this post as a {ARCHETYPES[GENERAL_ARCHETYPE].name}:" in prompt
    assert "EVENT (mandatory" not in prompt and "<event>" not in prompt.split("REDRAFT:")[0]
    assert f"<previous_post>\n{BODY}\n</previous_post>" in prompt        # the post with its markers, no envelope
    assert f"Text: {UNVERIFIED}" in _problems(prompt)
    assert state["current_draft"] == "<post>\nA redraft. [[V]]\n</post>"
    assert [d["node"] for d in state["draft_history"]] == ["draft", "redraft"]
    assert (record["redraft"]["input_tokens"], record["redraft"]["output_tokens"]) == (10, 10)


def test_the_redraft_sees_the_post_as_the_code_fixes_left_it(claude):
    post = "We rebuilt the ranker. [[S1]]\n\nIt felt like a verdict. [[V]]"
    feeling = dict(content="feeling_or_reaction", stated_as="authors_view", presented_as="author_did_or_experienced")
    state = _first_pass(claude, STORY_OUTPUT.format(event=UNVERIFIED, post=post), (OWN,), archetype=STORY_KEY,
                        changes={2: feeling})

    prompt = _redraft_prompt(claude, state)

    assert [fix["type"] for fix in state["review"]["fixes"]["code"]] == ["sentence_deleted"]
    assert "<previous_post>\nWe rebuilt the ranker. [[S1]]\n</previous_post>" in prompt
    assert [e["type"] for e in state["review"]["redraft"]["entries"]] == ["event_unverified"]


def test_a_cut_off_redraft_of_an_unverified_story_leaves_the_post_a_story(claude):
    state = _first_pass(claude, STORY_OUTPUT.format(event=UNVERIFIED, post="We rebuilt the ranker. [[S1]]"), (OWN,),
                        archetype=STORY_KEY)
    decision, post = state.get("archetype_decision"), state["current_draft"]

    prompt = _redraft_prompt(claude, state, reply=_cut_off("<post>\nWe rebuilt"))

    assert "EVENT (mandatory" not in prompt                              # the redraft was asked for a general post
    assert state["review"]["redraft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert (state["archetype"], state.get("archetype_decision"), state["current_draft"]) == (STORY_KEY, decision, post)
    assert [d["node"] for d in state["draft_history"]] == ["draft", "redraft_truncated"]


def test_a_verified_story_with_a_sentence_problem_takes_the_targeted_path_and_stays_a_story(claude):
    state = _first_pass(claude, STORY_OUTPUT.format(event=VERIFIED, post=BODY), (OWN,), archetype=STORY_KEY)

    record = state["review"]
    assert record["fixes"]["route"] == "targeted" and "redraft" not in record
    assert (record["targeted"]["flagged"], state["archetype"]) == ([2], STORY_KEY)


def test_a_stray_event_on_a_post_that_takes_none_is_redrafted_in_the_chosen_structure(claude):
    state = _first_pass(claude, STORY_OUTPUT.format(event=VERIFIED, post="We rebuilt the ranker. [[S1]]"), (OWN,),
                        archetype="contrarian_take")

    _redraft_prompt(claude, state)

    assert [i["type"] for i in state["review"]["first"]["acting"]] == ["event_unverified"]
    assert state["archetype"] == "contrarian_take" and "downgraded_from" not in state["review"]["redraft"]


def test_a_post_the_drafter_already_made_general_needs_no_redraft_for_its_event(claude):
    state = _first_pass(claude, STORY_OUTPUT.format(event="none", post=BODY), (OWN,), archetype=STORY_KEY)

    assert state["archetype"] == "general" and state["archetype_decision"]["downgraded_from"] == STORY_KEY
    assert state["review"]["fixes"]["route"] == "targeted"               # only the uncited line is left


def test_the_first_pass_issues_split_as_before(claude):
    marked = "Average revenue per account fell 4 percent and it stung. [[V]]\n\nThat is a fair trade. [[V]]"
    stung = {**FACT, "supported_by": ["S1"], "evidence": "average revenue per account fell 4 percent",
             "unsupported_part": "and it stung"}
    state = _first_pass(claude, marked, (PRICING, SURVEY), changes={1: stung},
                        rhythm={2: {"sentence": 2, "why": FREE_TEXT}})

    record = state["review"]
    assert [i["type"] for i in record["first"]["acting"]] == ["view_contains_specific", "not_in_sources", "wrong_citation"]
    assert [i["type"] for i in record["first"]["recorded"]] == ["ai_rhythm"]
    # The marker is fixed in code, which also settles the specific; the added words go to the targeted fix.
    assert [fix["type"] for fix in record["fixes"]["code"]] == ["marker_replaced"]
    assert [(e["type"], e["sentence"]) for e in record["targeted"]["entries"]] == [("not_in_sources", 1)]
    assert FREE_TEXT not in json.dumps(record["targeted"])
