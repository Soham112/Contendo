"""Perspective comes from the chunks' authorship; the frame rules in the prompt
match the frames the code produces; the profile and tone shape voice only."""

import pytest

from tests.conftest import CRITIC_ALL_STRONG
from tests.generation_fixtures import (
    ARTICLE, BURNOUT, INVESTOR_UPDATE, OBSERVED, OWN, PROFILE, USER, agent_sources, draft_prompt,
    last_prompt, make_state,
)


# --- Frames: the prompt matches the code ---------------------------------------------------

def _every_frame() -> set[str]:
    from utils.frames import chunk_frame

    frames = set()
    profiles = [{"role": r, "topics_of_expertise": t}
                for r in ("Junior analyst", "Analyst", "Principal engineer") for t in ([], ["statistics"])]
    chunks = [
        {"source_type": "consolidation"},
        *[{"memory_context": m, "source_type": s, "tags": "statistics"}
          for m in ("work", "personal_project", "observation", "learning", None)
          for s in ("note", "article")],
    ]
    for profile in profiles:
        frames |= {chunk_frame(chunk, profile) for chunk in chunks}
    return frames


def test_frame_list_is_exactly_what_the_code_can_produce():
    from utils.frames import FRAMES, SELF_FRAMES

    assert set(FRAMES) == _every_frame()
    assert len(FRAMES) == 9
    assert SELF_FRAMES <= set(FRAMES)
    assert all(frame.label and frame.rule for frame in FRAMES.values())


def test_draft_prompt_has_one_rule_per_frame_present_under_the_same_label(claude):
    from utils.frames import FRAMES

    prompt = draft_prompt(claude, make_state([OWN, ARTICLE, OBSERVED]))
    rules = prompt.split("SOURCE RULES (mandatory):", 1)[1].split("FABRICATION RULE:", 1)[0]
    knowledge_base = prompt.split("Knowledge base", 1)[1].split("Topic:", 1)[0]

    present = ["PERSONAL_WORK", "OBSERVATION", "LEARNING_MID"]
    for key in present:
        assert f"{FRAMES[key].label}:" in knowledge_base
        assert f"{FRAMES[key].label}:\n{FRAMES[key].rule}" in rules
    for key in set(FRAMES) - set(present):
        assert FRAMES[key].label not in prompt
    assert "three frames" not in prompt


def test_source_titles_never_reach_the_draft_prompt(claude):
    """Stopgap: stored metadata doesn't say whether a title is real, so none is shown."""
    prompt = draft_prompt(claude, make_state([OWN, ARTICLE, OBSERVED]))

    assert "[source: youtube | tags: statistics]" in prompt
    for chunk in (OWN, ARTICLE, OBSERVED):
        assert chunk["source_title"] not in prompt
    assert "title" not in prompt.split("Knowledge base", 1)[1].split("Topic:", 1)[0]


def test_external_sources_are_referred_to_by_type_and_subject():
    from utils.frames import FRAMES, PERSPECTIVES, SELF_FRAMES

    for key in ("EXPERT_OUTSIDER", "LEARNING_SENIOR", "LEARNING_MID", "LEARNING_JUNIOR"):
        assert '"an article on..."' in FRAMES[key].rule and "do not give it a title" in FRAMES[key].rule
    for key in ("learned", "mixed"):
        assert '"a talk on..."' in PERSPECTIVES[key]
    everything = " ".join([*(f.rule for f in FRAMES.values()), *PERSPECTIVES.values()])
    assert "by its title" not in everything and "credit" not in everything.lower()
    assert all("article on" not in FRAMES[key].rule for key in SELF_FRAMES)


def test_the_trace_still_records_source_titles_for_debugging():
    from pipeline.trace import build_trace_row

    row = build_trace_row(make_state([ARTICLE]), [])
    assert row["retrieved"][0]["source_title"] == "Forecast intervals talk"


# --- has_chunks drives the no-notes rule ------------------------------------------------------

def test_no_notes_rule_follows_the_has_chunks_flag(claude):
    without = draft_prompt(claude, make_state([], has_chunks=False))
    assert "NO NOTES RULE" in without
    assert "(No notes relevant to this topic were found.)" in without

    quoting = dict(OWN, text="My note says: No relevant knowledge base entries found. Draw on general expertise.")
    claude.reset()
    with_chunks = draft_prompt(claude, make_state([quoting]))
    assert "NO NOTES RULE" not in with_chunks  # a chunk that contains the old sentinel text changes nothing


def test_nothing_tells_the_model_to_draw_on_general_expertise(claude):
    assert "general expertise" not in draft_prompt(claude, make_state([], has_chunks=False)).lower()
    for name, source in agent_sources().items():
        assert "general expertise" not in source.lower(), name


def test_retrieval_node_sets_has_chunks(fake_db):
    from agents.retrieval_agent import retrieval_node

    state = retrieval_node({"topic": "anything", "context": "", "user_id": USER})
    assert state["has_chunks"] is False


# --- Perspective ---------------------------------------------------------------------------

@pytest.mark.parametrize("chunks,opinion_only,expected", [
    ([OWN], False, "experience"),
    ([ARTICLE, OBSERVED], False, "learned"),
    ([OWN, ARTICLE], False, "mixed"),
    ([], False, "opinion"),
    ([OWN], True, "opinion"),
])
def test_perspective_comes_from_chunk_authorship(chunks, opinion_only, expected):
    from utils.frames import decide_perspective

    assert decide_perspective(chunks, PROFILE, opinion_only=opinion_only) == expected


@pytest.mark.parametrize("overrides,expected", [
    ({}, "learned"),
    ({"no_specifics": True}, "opinion"),
    ({"coverage_gate": {"decision": "skipped_first_post"}}, "opinion"),
    ({"coverage_gate": {"decision": "pass"}, "first_post": True}, "learned"),
])
def test_plan_node_sets_the_perspective(overrides, expected):
    from pipeline.graph import plan_node

    assert plan_node(make_state([ARTICLE], **overrides))["perspective"] == expected


def test_learned_perspective_is_in_thedraft_prompt(claude):
    prompt = draft_prompt(claude, make_state([ARTICLE]))
    assert "PERSPECTIVE: learned." in prompt
    assert "without giving it a title" in prompt and '"a video about..."' in prompt
    assert "Do not connect the material to the author's own work, career or life" in prompt
    # The old rules that asked for an invented personal connection are gone.
    assert "Coming from X background" not in prompt and "Been going deep" not in prompt


@pytest.mark.parametrize("node", ["draft", "critic", "humanizer"])
def test_profile_content_never_reaches_a_writing_prompt(claude, node):
    from agents.critic_agent import critic_node
    from agents.humanizer_agent import humanizer_node

    if node == "draft":
        prompt = draft_prompt(claude, make_state([ARTICLE]))
    elif node == "critic":
        claude.queue(CRITIC_ALL_STRONG)
        critic_node(make_state([ARTICLE]))
        prompt = last_prompt(claude)
    else:
        claude.queue("Humanized.")
        humanizer_node(make_state([ARTICLE]))
        prompt = last_prompt(claude)

    for content in (PROFILE["bio"], PROFILE["opinions"][0], "Topics of expertise"):
        assert content not in prompt
    assert "Voice: dry" in prompt  # voice still does


def test_humanizer_keeps_the_perspective_and_adds_no_reactions(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue("Humanized.")
    humanizer_node(make_state([ARTICLE]))
    prompt = last_prompt(claude)
    assert "Keep the draft's perspective." in prompt
    assert "caught me off guard" not in prompt


@pytest.mark.parametrize("tone", ["casual", "technical", "storytelling"])
def test_tone_is_voice_only(tone):
    from utils.formatters import get_format_instructions

    text = get_format_instructions("linkedin post", "standard", tone)
    for structural in ("Open with a scene", "lesson learned", "Build tension", "Include specifics", "words"):
        assert structural not in text


# --- Writing samples: style, never a source -------------------------------------------------

@pytest.mark.parametrize("node", ["draft", "humanizer"])
def test_writing_samples_are_shown_as_style_examples_only(claude, node):
    from agents.humanizer_agent import humanizer_node
    from memory.profile_store import WRITING_SAMPLES_RULE

    assert WRITING_SAMPLES_RULE == ("These are examples of the author's style. "
                                    "Do not reuse any facts, numbers, names or events from them.")
    if node == "draft":
        prompt = draft_prompt(claude, make_state([ARTICLE]))
    else:
        claude.queue("Humanized.")
        humanizer_node(make_state([ARTICLE]))
        prompt = last_prompt(claude)

    sample = PROFILE["writing_samples"][0]
    assert f"Writing samples:\n  {WRITING_SAMPLES_RULE}\n  Sample 1:\n  {sample}" in prompt


def test_profile_without_samples_shows_no_samples_section():
    from memory.profile_store import WRITING_SAMPLES_RULE, profile_voice_context

    rendered = profile_voice_context({"name": "Mara", "writing_samples": []})
    assert "Writing samples" not in rendered and WRITING_SAMPLES_RULE not in rendered


# --- Facts from separate sources stay separate (prompt-only) -----------------------------------

CROSS_SOURCE = ("Never link facts from different sources as cause and effect, sequence or result "
                "unless one source states that link. Facts from separate notes stay separate.")


def _founder_06_state(**overrides):
    """The smoke-eval case that stitched two notes together: the post said investor intros rose
    "after the format change and having my co-founder in the loop". The intros figure is in the
    investor-update note; the co-founder and the format change are in the burnout note."""
    return make_state([BURNOUT, INVESTOR_UPDATE], topic="Noticing burnout before it runs you",
                      context="Keep it practical, no therapy-speak", tone="storytelling", **overrides)


def test_founder_06_draft_prompt_keeps_the_two_notes_as_separate_sources(claude):
    prompt = draft_prompt(claude, _founder_06_state())

    assert " ".join(CROSS_SOURCE.split()) in " ".join(prompt.split())
    assert "Each chunk above is a separate source." in prompt
    knowledge_base = prompt.split("Knowledge base", 1)[1].split("Topic:", 1)[0]
    # Each note sits under its own label, so the model can tell them apart.
    assert knowledge_base.index("OBSERVATION:") < knowledge_base.index("Last spring I burned out")
    assert knowledge_base.index("OWN EXPERIENCE: WORK:") < knowledge_base.index("three a month")
    assert "PERSPECTIVE: mixed." in prompt


def test_founder_06_critic_is_told_to_flag_links_between_separate_chunks(claude):
    from agents.critic_agent import critic_node

    stitched = ("After the format change and having my co-founder in the loop, investor intros went "
                "from one a quarter to three a month.")
    claude.queue(CRITIC_ALL_STRONG)
    critic_node(_founder_06_state(current_draft=stitched))
    prompt = last_prompt(claude)

    assert "If the draft links facts from different chunks as cause and effect, sequence or result" in prompt
    assert 'mark SUBSTANCE "needs_work" and say which link to remove' in prompt
    assert "[frame: OBSERVATION | authorship: external" in prompt
    assert "[frame: PERSONAL_WORK | authorship: self" in prompt
    assert stitched in prompt


def test_humanizer_may_not_add_a_link_the_draft_does_not_state(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue("Humanized.")
    humanizer_node(_founder_06_state())
    assert ("Never link facts as cause and effect, sequence or result unless the draft already states "
            "that link.") in last_prompt(claude)


def test_no_cross_source_rule_without_chunks(claude):
    assert "CROSS-SOURCE RULE" not in draft_prompt(claude, make_state([], has_chunks=False))


# --- No invented reactions, no unsupported generalisations (prompt-only) -------------------------

def test_reactions_rule_is_in_the_perspectives_that_draw_on_external_sources():
    from utils.frames import PERSPECTIVES

    rule = "Don't attribute feelings, reactions or habits to the author about a source"
    for key in ("learned", "mixed"):
        assert rule in PERSPECTIVES[key]
        assert "\"I haven't been able to put down\"" in PERSPECTIVES[key]
        assert "Present the source's idea and the author's view of it plainly." in PERSPECTIVES[key]
    for key in ("experience", "opinion"):
        assert rule not in PERSPECTIVES[key]


def test_generalisation_rule_is_in_every_perspective():
    from utils.frames import PERSPECTIVES

    assert set(PERSPECTIVES) == {"experience", "learned", "opinion", "mixed"}
    for text in PERSPECTIVES.values():
        assert "Don't make claims about what most people, most founders or most teams do unless a source says so" in text
        assert "\"I think many teams...\"" in text


def test_humanizer_gets_the_reactions_rule(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue("Humanized.")
    humanizer_node(make_state([ARTICLE]))
    assert "Don't attribute feelings, reactions or habits to the author about a source" in last_prompt(claude)
