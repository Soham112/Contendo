"""One length table and one target per post; nothing asks the model to count words."""

import re

import pytest

from tests.conftest import ARCHETYPE_GENERAL, CRITIC_ALL_STRONG
from tests.generation_fixtures import USER, agent_sources, draft_prompt, last_prompt, make_state, BACKEND


# --- One length table, one target per post -------------------------------------------

def test_word_ranges_live_in_one_place():
    for name, source in agent_sources().items():
        if name != "formatters.py":
            assert "_WORD_COUNT_MAP" not in source and "(250, 350)" not in source, name
    assert not (BACKEND / "utils" / "post_cleanup.py").exists()


LINKEDIN = {"min_words": 100, "max_words": 200, "write_max_words": 150, "may_expand": True, "basis": "linkedin"}
FIRST_POST = {"min_words": 70, "max_words": 115, "write_max_words": 100, "may_expand": False, "basis": "first_post"}
THIN = {"min_words": 0, "max_words": 200, "write_max_words": 150, "may_expand": False, "basis": "thin_sources"}


@pytest.mark.parametrize("kwargs,expected", [
    ({}, LINKEDIN),
    ({"first_post": True}, FIRST_POST),
    ({"thin_sources": True}, THIN),
    ({"first_post": True, "thin_sources": True}, FIRST_POST),
])
def test_resolve_length_target(kwargs, expected):
    from utils.formatters import resolve_length_target

    assert resolve_length_target("linkedin post", "standard", **kwargs) == expected


@pytest.mark.parametrize("length", ["", "concise", "standard", "long-form", "anything"])
def test_a_linkedin_post_ignores_the_requested_length(length):
    from utils.formatters import resolve_length_target

    assert resolve_length_target("linkedin post", length) == LINKEDIN
    assert resolve_length_target("", length) == LINKEDIN     # no format: a LinkedIn post


def test_a_post_stays_under_200_words_and_the_drafter_is_asked_for_less():
    from utils.formatters import LINKEDIN_MAX_WORDS, LINKEDIN_RANGE, resolve_length_target, word_count_rule

    target = resolve_length_target("linkedin post", "")
    assert target["max_words"] == LINKEDIN_MAX_WORDS == 200
    assert target["write_max_words"] == LINKEDIN_RANGE[1] < LINKEDIN_MAX_WORDS
    assert word_count_rule(target) == f"LENGTH: {LINKEDIN_RANGE[0]}–{LINKEDIN_RANGE[1]} words. Never go over {LINKEDIN_RANGE[1]}."


def test_other_formats_still_follow_the_requested_length():
    from utils.formatters import WORD_RANGES, resolve_length_target

    low, high = WORD_RANGES["medium article"]["long-form"]
    assert resolve_length_target("medium article", "long-form") == {
        "min_words": low, "max_words": high, "may_expand": True, "basis": "length_setting"}


def test_length_target_ignores_the_requested_length_for_a_first_post_and_skips_threads():
    from utils.formatters import resolve_length_target

    assert resolve_length_target("medium article", "long-form", first_post=True)["max_words"] == 100
    assert resolve_length_target("linkedin post", "", first_post=False)["min_words"] == 100
    assert resolve_length_target("thread", "standard", first_post=True) is None


def test_drafter_and_humanizer_get_the_same_length_rule(claude):
    from agents.humanizer_agent import humanizer_node
    from utils.formatters import resolve_length_target, word_count_rule

    target = resolve_length_target("linkedin post", "standard", first_post=True)
    rule = word_count_rule(target)
    assert rule == "LENGTH: 70–100 words. Never go over 100."

    draft_text = draft_prompt(claude, make_state(first_post=True, length_target=target))
    claude.queue("Humanized.")
    humanizer_node(make_state(first_post=True, length_target=target))

    assert rule in draft_text and rule in last_prompt(claude)
    for prompt in (draft_text, last_prompt(claude)):
        assert "120" not in prompt and "250" not in prompt and "350" not in prompt


def test_thin_sources_rule_has_a_ceiling_and_no_floor():
    from utils.formatters import resolve_length_target, word_count_rule

    rule = word_count_rule(resolve_length_target("linkedin post", "standard", thin_sources=True))
    assert "at most 150 words" in rule and "100" not in rule
    assert "Never pad" in rule
    assert word_count_rule(None) == ""


def _enforce(post, **target_kwargs):
    from agents.word_count_enforcer_agent import word_count_enforcer_node
    from utils.formatters import resolve_length_target

    return word_count_enforcer_node(make_state(
        current_draft=post, length_target=resolve_length_target("linkedin post", "standard", **target_kwargs)))


@pytest.mark.parametrize("target_kwargs", [{"first_post": True}, {"thin_sources": True}])
def test_enforcer_never_expands_a_first_or_thin_source_post(claude, target_kwargs):
    short = "A short post. " * 5  # 15 words: under every floor

    state = _enforce(short, **target_kwargs)

    assert claude.calls == []
    assert state["current_draft"] == short


def test_enforcer_still_expands_a_normal_post(claude):
    claude.queue("An expanded post.")
    state = _enforce("A short post.")
    assert state["current_draft"] == "An expanded post."
    assert "at least 100 words" in last_prompt(claude)


@pytest.mark.parametrize("target_kwargs,target_text", [
    ({"first_post": True}, "70–115 words"),       # pipeline A trims only past the hard limit
    ({"thin_sources": True}, "at most 200 words"),
])
def test_enforcer_still_trims_a_first_or_thin_source_post(claude, target_kwargs, target_text):
    claude.queue("A trimmed post.")
    state = _enforce("word " * 400, **target_kwargs)

    assert state["current_draft"] == "A trimmed post."
    assert f"Trim this post to {target_text}." in last_prompt(claude)


@pytest.mark.parametrize("post,action", [("A short post.", "Expand"), ("word " * 400, "Trim")])
def test_enforcer_prompts_ban_the_em_dash(claude, post, action):
    claude.queue("An adjusted post.")
    _enforce(post)

    prompt = last_prompt(claude)
    assert prompt.startswith(f"You are a precise editor. {action}")
    assert "Never use the em dash character (—) anywhere in the output." in prompt


def test_enforcer_does_nothing_without_a_target(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    state = word_count_enforcer_node(make_state(format="thread", length_target=None, current_draft="1/ a thread"))
    assert claude.calls == [] and state["current_draft"] == "1/ a thread"


def test_plan_node_sets_one_target_and_every_node_reads_it(monkeypatch):
    from pipeline.graph import plan_node

    first = plan_node(make_state(first_post=True, length="long-form", length_target=None))
    assert first["length_target"]["basis"] == "first_post"
    thin = plan_node(make_state(retrieval_confidence="low", length_target=None))
    assert thin["length_target"] == THIN
    for name in ("draft_prompt.py", "humanizer_agent.py", "word_count_enforcer_agent.py"):
        source = agent_sources()[name]
        assert 'state.get("length_target")' in source, name
        assert "resolve_length_target(" not in source, name  # nodes read the target; they never compute one


# --- No counting instructions -------------------------------------------------------------

def test_no_prompt_asks_the_model_to_count_words():
    banned = re.compile(r"count (your words )?before outputting|count your words|do not print the word count", re.I)
    for name, source in agent_sources().items():
        assert not banned.search(source), name


# --- Through the whole pipeline -------------------------------------------------------------------

def test_first_post_runs_to_its_own_target_and_is_never_expanded(claude, fake_db):
    from pipeline.graph import run_pipeline

    # No posts and no notes: a first post. Seven words is far under 70, and stays that way.
    claude.queue(ARCHETYPE_GENERAL, "A short first post that stays short.", CRITIC_ALL_STRONG,
                 "A short first post that stays short.", "CLEAN", "A short first post that stays short.")
    result = run_pipeline(topic="Forecast intervals", format="linkedin post", tone="storytelling",
                          context="Core opinion/take: intervals beat point forecasts", user_id=USER)

    assert result["post"] == "A short first post that stays short."
    [trace] = fake_db.tables["generation_traces"]
    outputs = trace["node_outputs"]
    assert outputs["length_target"] == FIRST_POST
    assert outputs["perspective"] == "opinion"
    assert outputs["archetype_decision"]["allowed"] == ["contrarian_take", "teach_me_something", "general"]
    assert "word_count_enforcer" not in [c["event_type"] for c in trace["llm_calls"]]
    draft_prompt = claude.calls[1]["messages"][-1]["content"]
    assert "LENGTH: 70–100 words." in draft_prompt and "PERSPECTIVE: opinion." in draft_prompt
