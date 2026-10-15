"""Variant D (one call): the drafter chooses the structure among the types the
code allows and names it in a <structure> part; no separate structure call.
D-Opus-low is the same at effort "low" (Opus 5.5 cannot turn thinking off)."""
import pytest

from tests.test_generation_trace import USER, _only_trace, seeded_kb  # noqa: F401


from tests.generation_fixtures import one_call_reply as _one_call  # noqa: E402


def _run(variant="D-Opus"):
    from pipeline.graph import run_pipeline
    return run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER, variant=variant)


@pytest.mark.parametrize("variant,effort", [("D-Opus", "medium"), ("D-Opus-low", "low")])
def test_a_one_call_run_makes_one_draft_call_and_no_structure_call(claude, fake_db, seeded_kb, variant, effort):
    claude.queue(_one_call("pgvector makes retrieval fast. [[S1]]", "teach_me_something"))

    result = _run(variant)

    assert result["status"] == "ok" and result["post"] == "pgvector makes retrieval fast."
    trace = _only_trace(fake_db)
    [call] = trace["llm_calls"]
    assert (call["event_type"], call["model"], call["effort"]) == ("generate", "claude-opus-5-5", effort)
    outputs = trace["node_outputs"]
    assert [t["step"] for t in outputs["step_timings"]] == [
        "load_profile", "retrieval", "plan", "draft", "read_structure", "strip", "finalise", "checks"]
    decision = outputs["archetype_decision"]
    assert (decision["archetype"], decision["chosen"], decision["chosen_by"]) == ("teach_me_something", "teach_me_something", "drafter")
    assert "draft_format" not in outputs


def test_the_prompt_offers_only_the_types_the_code_allows(claude, fake_db, seeded_kb):
    from agents.archetype_agent import allowed_archetypes
    from utils.formatters import ARCHETYPES

    claude.queue(_one_call("pgvector makes retrieval fast. [[S1]]"))
    _run()

    prompt = claude.calls[0]["messages"][-1]["content"]
    allowed = _only_trace(fake_db)["node_outputs"]["archetype_decision"]["allowed"]
    assert allowed and set(allowed) <= set(ARCHETYPES)
    for key in ARCHETYPES:
        assert (f'<type key="{key}">' in prompt) == (key in allowed)
    assert "<structure>" in prompt and "POST STRUCTURE: choose one" in prompt
    # Opinion (no notes): the gate leaves no story type, so there is no EVENT rule.
    assert allowed_archetypes("opinion", 0) == [k for k in ARCHETYPES if k in ("contrarian_take", "teach_me_something", "general")]


@pytest.mark.parametrize("structure,reason", [("made_up", "not an allowed type for these sources"),
                                              (None, "no structure named")])
def test_a_structure_outside_the_allowed_set_becomes_general(claude, fake_db, seeded_kb, structure, reason):
    claude.queue(_one_call("pgvector makes retrieval fast. [[S1]]", structure))

    result = _run()

    assert result["status"] == "ok" and result["post"] == "pgvector makes retrieval fast."
    outputs = _only_trace(fake_db)["node_outputs"]
    decision = outputs["archetype_decision"]
    assert (decision["archetype"], decision["downgraded_from"], decision["reason"]) == ("general", structure, reason)
    kinds = [f["kind"] for f in outputs.get("draft_format", [])]
    assert kinds == ([] if structure else ["structure_missing"])


def _state(draft: str, allowed: list[str]) -> dict:
    return {"current_draft": draft, "draft_history": [{"node": "draft"}],
            "archetype_decision": {"allowed": allowed, "chosen_by": "drafter"}}


def test_read_structure_keeps_an_allowed_story_type_and_leaves_the_event_for_strip():
    from pipeline.finalise import read_structure_node, strip_draft_node

    draft = _one_call("I shipped it. [[S1]]", "incident_report", 'S1 | "We shipped the fix on Monday."')
    state = read_structure_node(_state(draft, ["incident_report", "general"]))

    assert state["archetype"] == "incident_report" and "<structure>" not in state["current_draft"]
    state = strip_draft_node(state)
    assert (state["event"]["status"], state["event"]["source"]) == ("cited", "S1")
    assert state["current_draft"] == "I shipped it. [[S1]]"


def test_read_structure_records_a_repeated_part_and_uses_the_first():
    from pipeline.finalise import read_structure_node

    draft = "<structure>Teach_Me_Something</structure>\n<structure>general</structure>\n<post>\nx [[V]]\n</post>"
    state = read_structure_node(_state(draft, ["teach_me_something", "general"]))

    assert state["archetype"] == "teach_me_something"
    assert [f["kind"] for f in state["draft_format"]] == ["structure_repeated"]
    assert state["current_draft"] == "<post>\nx [[V]]\n</post>"


def test_the_c_prompt_still_names_one_structure():
    from agents.draft_prompt import build_cited_prompt

    state = {"profile": {}, "format": "linkedin post", "tone": "casual", "topic": "t", "user_id": "u",
             "archetype": "teach_me_something", "retrieval_bundle": {"chunks": []}}
    prompt, _ = build_cited_prompt(state)

    assert "POST STRUCTURE: write this post as a " in prompt
    assert "<structure>" not in prompt and "<type key=" not in prompt


def test_with_no_variant_configured_a_run_is_d_opus_low_with_one_low_effort_call(claude, fake_db, seeded_kb, monkeypatch):
    from pipeline.graph import run_pipeline

    monkeypatch.delenv("PIPELINE_VARIANT", raising=False)
    claude.queue(_one_call("pgvector makes retrieval fast. [[S1]]", "teach_me_something"))

    result = run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER)

    assert result["status"] == "ok" and result["post"] == "pgvector makes retrieval fast."
    trace = _only_trace(fake_db)
    assert trace["node_outputs"]["variant"] == "D-Opus-low"
    assert [(c["event_type"], c["effort"]) for c in trace["llm_calls"]] == [("generate", "low")]


def test_pipeline_variant_c_opus_still_runs_as_the_rollback(claude, fake_db, seeded_kb, monkeypatch):
    from pipeline.graph import run_pipeline
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped

    monkeypatch.setenv("PIPELINE_VARIANT", "C-Opus")
    claude.queue(ARCHETYPE_GENERAL, enveloped("pgvector makes retrieval fast. [[S1]]"))

    result = run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER)

    assert result["status"] == "ok" and result["post"] == "pgvector makes retrieval fast."
    trace = _only_trace(fake_db)
    assert trace["node_outputs"]["variant"] == "C-Opus"
    assert [(c["event_type"], c["effort"]) for c in trace["llm_calls"]] == [("archetype", None), ("generate", "medium")]


def test_pipeline_variant_a_still_runs_as_the_rollback(claude, fake_db, seeded_kb, monkeypatch):
    from pipeline.graph import run_pipeline
    from tests.test_generation_trace import STANDARD_RUN

    monkeypatch.setenv("PIPELINE_VARIANT", "A")
    claude.queue(*STANDARD_RUN)

    result = run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER)

    assert result["post"]
    assert _only_trace(fake_db)["node_outputs"]["variant"] == "A"
