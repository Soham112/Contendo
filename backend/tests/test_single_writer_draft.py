"""The single-writer drafter (variants B and C): structure-only archetype choice,
the cited draft prompt, one draft call with no guard retry, and the strip and
finalise steps that remove the EVENT line and the markers. Length, trimming and
truncation are in test_finalise_and_trim.py."""

import json

import pytest

from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import ARTICLE, OBSERVED, OWN, PROFILE, STORY, last_prompt, make_state
from tests.test_generation_trace import USER as KB_USER, seeded_kb  # noqa: F401  (shared knowledge-base fixture)

STORY_KEY = "before_after"
EVENT_LINE = 'EVENT: S1 | "We rebuilt the ranker in March and latency fell."'


def _structure(key: str) -> str:
    return json.dumps({"archetype": key})


def _draft(claude, state, reply="The post. [[V]]"):
    """Run the cited draft call on state; return (state, the prompt it sent)."""
    from agents.draft_agent import cited_draft_node

    claude.queue(reply)
    cited_draft_node(state)
    return state, last_prompt(claude)


# --- Structure choice ---------------------------------------------------------

def test_the_structure_choice_asks_for_a_key_only():
    from agents.archetype_agent import StructureChoice

    assert set(StructureChoice.model_json_schema()["properties"]) == {"archetype"}


def test_the_structure_choice_is_one_haiku_call_and_names_no_event(claude):
    from agents.draft_agent import structure_node

    claude.queue(_structure(STORY_KEY))
    state = structure_node(make_state([OWN, ARTICLE]))

    [call] = claude.calls
    assert call["model"] == "claude-haiku-4-5-20251001"
    assert set(call["tools"][0]["input_schema"]["properties"]) == {"archetype"}
    assert state["archetype"] == STORY_KEY
    assert state["archetype_decision"] == {
        "archetype": STORY_KEY, "chosen": STORY_KEY, "downgraded_from": None, "reason": None,
        "allowed": state["archetype_decision"]["allowed"],
    }


@pytest.mark.parametrize("chunks,overrides", [
    ([OWN, ARTICLE], {}),
    ([ARTICLE], {}),
    ([OBSERVED], {}),
    ([], {}),
    ([OWN], {"perspective": "opinion"}),
])
def test_both_choices_offer_the_same_source_gated_set(claude, chunks, overrides):
    from agents.archetype_agent import choose_archetype, choose_structure

    claude.queue(ARCHETYPE_GENERAL, ARCHETYPE_GENERAL)
    for_a = choose_archetype(make_state(chunks, **overrides))
    for_single_writer = choose_structure(make_state(chunks, **overrides))

    assert for_single_writer["allowed"] == for_a["allowed"]
    assert bool(STORY & set(for_single_writer["allowed"])) == (bool(chunks == [OWN, ARTICLE]))


def test_a_story_structure_is_not_offered_without_an_own_note_and_is_refused_if_chosen(claude):
    from agents.archetype_agent import choose_structure

    claude.queue(_structure("personal_story"))
    decision = choose_structure(make_state([ARTICLE]))

    assert decision["archetype"] == "general"
    assert decision["downgraded_from"] == "personal_story"
    assert "personal_story" not in decision["allowed"]


def test_a_failed_structure_call_gets_general_and_says_why(claude):
    from agents.archetype_agent import choose_structure

    claude.queue("not a tool call", "still not a tool call")
    decision = choose_structure(make_state([OWN]))

    assert decision["archetype"] == "general" and decision["chosen"] is None
    assert decision["reason"].startswith("inference failed")


# --- The cited draft prompt -----------------------------------------------------------

def test_the_prompt_shows_the_sources_block_with_its_data_rule(claude):
    from utils.frames import SOURCES_ARE_DATA_RULE, build_sources_block

    state, prompt = _draft(claude, make_state([OWN, ARTICLE], archetype="general"))

    block = build_sources_block([OWN, ARTICLE], PROFILE)
    assert block.text in prompt
    assert SOURCES_ARE_DATA_RULE in prompt
    assert prompt.index(SOURCES_ARE_DATA_RULE) < prompt.index(block.text)
    assert state["source_index"] == block.index
    assert state["draft_frame_block"] == block.text


def test_the_prompt_never_shows_titles_or_the_grouped_knowledge_base(claude):
    from utils.frames import format_chunks_by_frame

    _, prompt = _draft(claude, make_state([OWN, ARTICLE], archetype="general"))

    assert OWN["source_title"] not in prompt and ARTICLE["source_title"] not in prompt
    assert format_chunks_by_frame([OWN, ARTICLE], PROFILE) not in prompt


def test_the_prompt_carries_the_one_style_constant_the_humanizer_also_uses(claude):
    from agents.humanizer_agent import humanizer_node
    from utils.formatters import STYLE_RULES

    profile = {**PROFILE, "words_to_avoid": ["synergy", "leverage"]}
    style = STYLE_RULES.format(words_to_avoid="synergy, leverage")

    _, draft_prompt = _draft(claude, make_state([OWN], archetype="general", profile=profile))
    claude.queue("Humanized.")
    humanizer_node(make_state([OWN], profile=profile))

    assert style in draft_prompt
    assert style in last_prompt(claude)


@pytest.mark.parametrize("chunks,perspective", [([OWN], "experience"), ([ARTICLE], "learned"), ([OWN, ARTICLE], "mixed")])
def test_the_prompt_carries_the_perspective_and_one_rule_per_source_kind(claude, chunks, perspective):
    from utils.frames import PERSPECTIVES, frame_rules

    state = make_state(chunks, archetype="general")
    assert state["perspective"] == perspective
    _, prompt = _draft(claude, state)

    assert PERSPECTIVES[perspective] in prompt
    assert frame_rules(chunks, PROFILE) in prompt


def test_the_prompt_carries_the_structure_only_and_the_one_length_rule(claude):
    from utils.formatters import ARCHETYPES, resolve_length_target, word_count_rule

    target = resolve_length_target("linkedin post", "concise")
    _, prompt = _draft(claude, make_state([OWN], archetype="contrarian_take", length="concise", length_target=target))

    assert ARCHETYPES["contrarian_take"].structure in prompt
    assert ARCHETYPES["contrarian_take"].fits not in prompt
    assert word_count_rule(target) in prompt
    assert sum(word_count_rule(resolve_length_target("linkedin post", length)) in prompt
               for length in ("concise", "standard", "long-form")) == 1


def test_the_prompt_uses_the_voice_only_profile(claude):
    from memory.profile_store import profile_voice_context

    _, prompt = _draft(claude, make_state([OWN], archetype="general"))

    assert profile_voice_context(PROFILE) in prompt
    assert PROFILE["bio"] not in prompt and PROFILE["opinions"][0] not in prompt


def test_every_marker_form_the_prompt_names_is_one_the_code_accepts(claude):
    from utils.citations import leftover_markers

    _, prompt = _draft(claude, make_state([OWN, ARTICLE], archetype="general"))

    found = leftover_markers(prompt)
    assert {f.text for f in found} >= {"[[S2]]", "[[S1,S3]]", "[[R]]", "[[V]]"}
    assert {f.kind for f in found} == {"leftover"}  # every one is a valid marker


@pytest.mark.parametrize("key", sorted(STORY))
def test_a_story_structure_asks_for_the_event_line_and_offers_the_general_structure(claude, key):
    from utils.citations import parse_event_header
    from utils.formatters import ARCHETYPES

    _, prompt = _draft(claude, make_state([OWN], archetype=key))

    assert ARCHETYPES[key].structure in prompt
    assert ARCHETYPES["general"].structure in prompt
    event_lines = [line for line in prompt.splitlines() if line.startswith("EVENT:")]
    assert "EVENT: none" in event_lines
    # The other form is shown with placeholders only: it is not itself a usable EVENT line.
    assert all(parse_event_header(line, required=True).status in ("none", "malformed") for line in event_lines)


@pytest.mark.parametrize("key", ["general", "contrarian_take", "teach_me_something", "list_that_isnt", "prediction_bet"])
def test_other_structures_do_not_ask_for_an_event_line(claude, key):
    _, prompt = _draft(claude, make_state([OWN], archetype=key))

    assert not [line for line in prompt.splitlines() if line.startswith("EVENT:")]


def test_with_no_sources_the_prompt_says_so_and_the_index_is_empty(claude):
    from utils.frames import NO_CHUNKS_BLOCK

    state, prompt = _draft(claude, make_state([], archetype="general"))

    assert NO_CHUNKS_BLOCK in prompt
    assert state["source_index"] == {}


# --- The draft call ---------------------------------------------------------------

def test_the_draft_is_one_sonnet_call_stored_exactly_as_written(claude):
    reply = f"{EVENT_LINE}\n\nWe rebuilt the ranker in March. [[S1]]\n\nIt was worth it. [[V]]"

    state, _ = _draft(claude, make_state([OWN], archetype=STORY_KEY), reply)

    [call] = claude.calls
    assert call["model"] == "claude-sonnet-4-6"
    assert state["current_draft"] == reply
    assert state["draft_history"] == [{"node": "draft", "iteration": 0, "text": reply}]


def test_unsupported_specifics_cause_no_retry_and_no_sentence_removal(claude):
    # Pipeline A's guard would retry this draft (37% and Tuesday are in no source) and then drop the sentence.
    reply = "Latency fell 37% on a Tuesday. [[S1]]\n\nIt was worth it. [[V]]"

    state, _ = _draft(claude, make_state([OWN], archetype="general"), reply)

    assert len(claude.calls) == 1
    assert state["current_draft"] == reply
    assert "specifics_guard" not in state


# --- Strip --------------------------------------------------------------------

def _strip(marked: str, archetype: str, **decision):
    """strip (EVENT line) then finalise (markers), as the graph runs them."""
    from pipeline.finalise import finalise_draft_node, strip_draft_node

    state = make_state([OWN, ARTICLE], archetype=archetype, current_draft=marked,
                       archetype_decision={"archetype": archetype, "chosen": archetype, "allowed": [archetype, "general"],
                                           "downgraded_from": None, "reason": None, **decision})
    return finalise_draft_node(strip_draft_node(state))


def test_strip_alone_removes_only_the_event_line():
    from pipeline.finalise import strip_draft_node

    state = strip_draft_node(make_state([OWN], archetype=STORY_KEY,
                                        current_draft=f"{EVENT_LINE}\n\nWe rebuilt the ranker. [[S1]]"))

    assert state["current_draft"] == "We rebuilt the ranker. [[S1]]"
    assert state["event"]["status"] == "cited"
    assert "final_post" not in state


def test_strip_removes_markers_and_the_event_line_and_records_both():
    state = _strip(f"{EVENT_LINE}\n\nWe rebuilt the ranker in March. [[S1]]\n\nThe talk agrees. [[S2]] So do I. [[V]]", STORY_KEY)

    assert state["final_post"] == "We rebuilt the ranker in March.\n\nThe talk agrees. So do I."
    assert state["current_draft"] == state["final_post"]
    assert state["event"] == {"status": "cited", "source": "S1",
                              "quote": "We rebuilt the ranker in March and latency fell.", "line": EVENT_LINE}
    assert [(c["text"], c["basis"], c["sources"]) for c in state["citations"]] == [
        ("We rebuilt the ranker in March.", "sources", ["S1"]),
        ("The talk agrees.", "sources", ["S2"]),
        ("So do I.", "view", []),
    ]
    for c in state["citations"]:
        assert state["final_post"][c["start"]:c["end"]] == c["text"]
    assert state["citation_failures"] == []
    assert state["archetype"] == STORY_KEY


def test_event_none_makes_the_post_general_and_the_decision_says_why():
    state = _strip("EVENT: none\n\nMost teams skip this. [[V]]", STORY_KEY)

    assert state["final_post"] == "Most teams skip this."
    assert state["event"]["status"] == "none"
    assert state["archetype"] == "general"
    assert state["archetype_decision"]["archetype"] == "general"
    assert state["archetype_decision"]["downgraded_from"] == STORY_KEY
    assert state["archetype_decision"]["chosen"] == STORY_KEY
    assert state["archetype_decision"]["reason"]


@pytest.mark.parametrize("marked,status", [
    ("We rebuilt the ranker. [[S1]]", "missing"),
    ("EVENT: the rebuild\n\nWe rebuilt the ranker. [[S1]]", "malformed"),
])
def test_a_failed_event_line_is_recorded_and_never_reaches_the_post(marked, status):
    state = _strip(marked, STORY_KEY)

    assert state["event"]["status"] == status
    assert state["final_post"] == "We rebuilt the ranker."
    assert state["archetype"] == STORY_KEY  # acting on the failure is for the checks, not this step


def test_marker_failures_are_recorded_with_where_they_were():
    state = _strip("A cited line. [[S1]]\nA line with a bad marker. [[S1 and S2]]\nA line with none.", "general")

    assert state["final_post"] == "A cited line.\nA line with a bad marker.\nA line with none."
    assert [(f["kind"], f["text"]) for f in state["citation_failures"]] == [("malformed", "[[S1 and S2]]")]
    assert [c["basis"] for c in state["citations"]] == ["sources", "uncited", "uncited"]
    assert state["event"]["status"] == "absent"


# --- Through run_pipeline ---------------------------------------------------------

def _run(variant, **overrides):
    from pipeline.graph import run_pipeline

    kwargs = dict(topic="pgvector retrieval", format="linkedin post", tone="casual", user_id=KB_USER, variant=variant)
    kwargs.update(overrides)
    return run_pipeline(**kwargs)


@pytest.mark.parametrize("variant", ["B", "C"])
@pytest.mark.parametrize("quality", ["draft", "standard", "polished"])
def test_a_run_is_two_calls_and_returns_the_post_without_markers(claude, fake_db, seeded_kb, variant, quality):
    marked = "pgvector makes retrieval fast. [[S1]]\n\nThat is most of the argument. [[V]]"
    claude.queue(ARCHETYPE_GENERAL, marked)

    result = _run(variant, quality=quality)

    assert [(c["model"], bool(c.get("tools"))) for c in claude.calls] == [
        ("claude-haiku-4-5-20251001", True), ("claude-sonnet-4-6", False)]
    assert result["status"] == "ok"
    assert result["post"] == "pgvector makes retrieval fast.\n\nThat is most of the argument."
    assert result["archetype"] == "general"
    assert result.get("fact_check_job") is None


def test_the_trace_records_what_the_drafter_cited(claude, fake_db, seeded_kb):
    marked = "pgvector makes retrieval fast. [[S1]]\n\nThat is most of the argument. [[V]] Loose end. [S1]"
    claude.queue(ARCHETYPE_GENERAL, marked)

    result = _run("B")

    [trace] = fake_db.tables["generation_traces"]
    outputs = trace["node_outputs"]
    assert outputs["variant"] == "B"
    assert outputs["draft_history"] == [{"node": "draft", "iteration": 0, "text": marked}]
    assert outputs["final_post"] == result["post"]
    assert "[[" not in outputs["final_post"]
    assert outputs["event"] == {"status": "absent", "source": None, "quote": None, "line": ""}
    assert [(f["kind"], f["text"]) for f in outputs["citation_failures"]] == [("single_brackets", "[S1]")]
    assert [c["basis"] for c in outputs["citations"]] == ["sources", "view", "uncited"]
    # The index numbers the retrieved chunks in the order the trace stores them.
    assert list(outputs["source_index"]) == [f"S{i + 1}" for i in range(len(trace["retrieved"]))]
    for entry in outputs["source_index"].values():
        assert trace["retrieved"][entry["position"]]["chunk_id"] == entry["chunk_id"]
    assert outputs["draft_frame_block"].startswith("<sources>")
    assert [c["event_type"] for c in trace["llm_calls"]] == ["archetype", "generate"]


def test_a_variant_a_trace_has_none_of_the_single_writer_fields(claude, fake_db, seeded_kb):
    from tests.test_generation_trace import STANDARD_RUN

    claude.queue(*STANDARD_RUN)
    _run("A")

    [trace] = fake_db.tables["generation_traces"]
    assert not {"source_index", "event", "citations", "citation_failures"} & set(trace["node_outputs"])
    assert "event_note" in trace["node_outputs"]["archetype_decision"]


def test_low_coverage_still_stops_before_any_call(claude, fake_db, seeded_kb):
    result = _run("B", topic="Autoscaling Kubernetes clusters for GPU inference")

    assert result["status"] == "low_coverage"
    assert claude.calls == []
