"""Every Claude call site goes through llm.client.complete() and logs usage
with its event_type, model label, and the caller's user_id."""

import inspect
import pathlib

import pytest

USER = "user-x"


@pytest.fixture
def usage_calls(monkeypatch):
    import llm.client as llm_client

    calls: list[dict] = []
    monkeypatch.setattr(llm_client, "schedule_usage_event", lambda **kw: calls.append(kw))
    return calls


def _events(usage_calls):
    return [(c["event_type"], c["model"]) for c in usage_calls]


def _assert_user(usage_calls, user_id=USER):
    assert usage_calls, "no usage logged"
    assert {c["user_id"] for c in usage_calls} == {user_id}


# --- Pipeline nodes -----------------------------------------------------------

def test_draft_node_logs_archetype_and_generate_with_metadata(claude, usage_calls):
    from agents.draft_agent import draft_node

    claude.queue("contrarian_take", "the draft")
    state = {"user_id": USER, "profile": {}, "format": "linkedin post", "tone": "casual", "topic": "t"}
    draft_node(state)

    assert _events(usage_calls) == [("archetype", "haiku"), ("generate", "sonnet")]
    assert usage_calls[1]["metadata"] == {"topic": "t", "format": "linkedin post", "archetype": "contrarian_take"}
    _assert_user(usage_calls)


def test_humanizer_node_logs_humanize(claude, usage_calls):
    from agents.humanizer_agent import humanizer_node

    claude.queue("humanized")
    humanizer_node({"user_id": USER, "profile": {}, "current_draft": "d", "quality": "standard"})
    assert _events(usage_calls) == [("humanize", "sonnet")]
    _assert_user(usage_calls)


def test_predictability_audit_keeps_step_event_types_and_labels(claude, usage_calls):
    from agents.predictability_audit_agent import predictability_audit_node

    claude.queue("One sentence here.", "A better one.", "final post")
    state = {"user_id": USER, "current_draft": "One sentence here. Another one.", "quality": "standard"}
    predictability_audit_node(state)

    assert state["current_draft"] == "final post"
    assert _events(usage_calls) == [
        ("predictability_audit_step1", "haiku"),
        ("predictability_audit_step2", "sonnet"),
        ("predictability_audit_step3", "haiku"),
    ]
    _assert_user(usage_calls)


def test_word_count_enforcer_logs(claude, usage_calls):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    claude.queue("expanded post")
    state = {"user_id": USER, "current_draft": "too short", "format": "linkedin post",
             "length": "standard", "quality": "standard"}
    word_count_enforcer_node(state)
    assert _events(usage_calls) == [("word_count_enforcer", "haiku")]
    _assert_user(usage_calls)


def test_scorer_node_passes_state_user_id(claude, usage_calls):
    from agents.scorer_agent import scorer_node

    claude.queue('{"total_score": 80}')
    scorer_node({"user_id": USER, "current_draft": "d", "quality": "polished"})
    assert _events(usage_calls) == [("score", "sonnet")]
    _assert_user(usage_calls)


# --- Standalone agent functions -----------------------------------------------

def _refine_draft():
    from agents.humanizer_agent import refine_draft
    refine_draft("draft", "fix it", profile={}, user_id=USER)


def _refine_selection():
    from agents.humanizer_agent import refine_selection
    refine_selection("sel", "shorter", "full post", user_id=USER)


def _score_text():
    from agents.scorer_agent import score_text
    score_text("draft", user_id=USER)


def _resume_ideas():
    from agents.ideation_agent import _generate_from_resume
    _generate_from_resume(3, None, "profile", "experience", "none", user_id=USER)


def _extract_tags():
    from agents.ingestion_agent import _extract_tags
    _extract_tags("some text", user_id=USER)


def _source_summary():
    from agents.ingestion_agent import _generate_source_summary
    _generate_source_summary("some text", user_id=USER)


def _classify_context():
    from agents.ingestion_agent import _classify_memory_context
    _classify_memory_context("some text", user_id=USER)


def _extract_entities():
    from agents.ingestion_agent import _extract_entities_for_chunk
    _extract_entities_for_chunk("some text", user_id=USER)


def _vision():
    from agents.vision_agent import extract_from_image
    extract_from_image("data:image/png;base64,AAAA", media_type="image/png", user_id=USER)


def _svg():
    from agents.visual_agent import generate_svg_for_diagram
    generate_svg_for_diagram("a flow", user_id=USER)


def _visuals():
    from agents.visual_agent import generate_visuals
    generate_visuals("Post.\n\n[DIAGRAM: a flow]", user_id=USER)


@pytest.mark.parametrize("call,expected", [
    (_refine_draft, ("refine", "sonnet")),
    (_refine_selection, ("refine_selection", "sonnet")),
    (_score_text, ("score", "sonnet")),
    (_resume_ideas, ("ideation", "sonnet")),
    (_extract_tags, ("ingest_tags", "sonnet")),
    (_source_summary, ("ingest_summary", "haiku")),
    (_classify_context, ("memory_context_classify", "haiku")),
    (_extract_entities, ("ingest_entities", "haiku")),
    (_vision, ("vision_extract", "sonnet")),
    (_svg, ("visual_svg", "sonnet")),
    (_visuals, ("visual_svg", "sonnet")),
], ids=lambda v: v.__name__.strip("_") if callable(v) else None)
def test_call_site_logs_usage(claude, usage_calls, call, expected):
    claude.queue("<svg></svg>")  # valid for the SVG sites; plain text for the rest
    call()
    assert _events(usage_calls) == [expected]
    _assert_user(usage_calls)


def test_resume_ideation_keeps_its_metadata(claude, usage_calls):
    claude.queue("ok")
    _resume_ideas()
    assert usage_calls[0]["metadata"] == {"count": 3, "topic": "", "source": "resume_fallback"}


def test_consolidate_entity_logs(claude, usage_calls, monkeypatch):
    import agents.consolidation_agent as consolidation

    monkeypatch.setattr(consolidation, "get_chunk_ids_for_entity", lambda entity_id, user_id: ["c1"])
    monkeypatch.setattr(consolidation, "get_chunks_by_ids",
                        lambda ids, user_id: [{"text": "hello world", "memory_context": "work"}])
    monkeypatch.setattr(consolidation, "upsert_consolidation_chunk", lambda **kw: None)

    claude.queue("brief")
    consolidation.consolidate_entity("e1", "Kafka", USER)
    assert _events(usage_calls) == [("consolidation", "haiku")]
    _assert_user(usage_calls)


def test_ingest_content_passes_user_id_to_every_claude_call(claude, usage_calls):
    from agents.ingestion_agent import ingest_content

    claude.respond_with(lambda kw: "[]")
    ingest_content("Some notes about building a data pipeline. " * 20, source_type="note", user_id=USER)

    events = {e for e, _ in _events(usage_calls)}
    assert {"ingest_tags", "memory_context_classify", "ingest_summary", "ingest_entities"} <= events
    _assert_user(usage_calls)


# --- Routers ------------------------------------------------------------------

def test_extract_resume_logs_with_authenticated_user(client, claude, usage_calls, monkeypatch, auth_headers):
    import routers.profile as profile_router

    monkeypatch.setattr(profile_router, "extract_from_pdf", lambda data: "resume text " * 20)
    claude.queue('{"profile": {}, "experience_nodes": []}')
    resp = client.post(
        "/extract-resume",
        files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_headers("user-r"),
    )
    assert resp.status_code == 200
    assert _events(usage_calls) == [("resume_extract", "sonnet")]
    _assert_user(usage_calls, "user-r")


@pytest.mark.parametrize("path,body,expected", [
    ("/score", {"post_content": "p"}, [("score", "sonnet")]),
    ("/refine", {"current_draft": "d", "refinement_instruction": "i"}, [("refine", "sonnet"), ("score", "sonnet")]),
    ("/suggest-memory-context", {"content": "some text"}, [("memory_context_classify", "haiku")]),
])
def test_router_passes_authenticated_user_id(client, claude, usage_calls, auth_headers, path, body, expected):
    claude.respond_with(lambda kw: '{"total_score": 70}')
    resp = client.post(path, json=body, headers=auth_headers("user-r"))
    assert resp.status_code == 200
    assert _events(usage_calls) == expected
    _assert_user(usage_calls, "user-r")


# --- Guards -------------------------------------------------------------------

def _threaded_functions():
    from agents import draft_agent, humanizer_agent, ingestion_agent, scorer_agent, vision_agent, visual_agent

    return [
        draft_agent.infer_archetype, humanizer_agent.refine_draft, scorer_agent.score_text,
        ingestion_agent._extract_tags, ingestion_agent._generate_source_summary,
        ingestion_agent._classify_memory_context, ingestion_agent._extract_entities_for_chunk,
        vision_agent.extract_from_image, visual_agent.generate_svg_for_diagram, visual_agent.generate_visuals,
    ]


def test_user_id_is_a_required_keyword_argument():
    for fn in _threaded_functions():
        param = inspect.signature(fn).parameters["user_id"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, fn.__name__
        assert param.default is inspect.Parameter.empty, fn.__name__


def test_no_model_strings_or_anthropic_clients_outside_llm():
    backend = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in backend.rglob("*.py"):
        rel = path.relative_to(backend)
        if rel.parts[0] in ("venv", "tests", "llm") or "site-packages" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ("claude-sonnet", "claude-haiku", "anthropic.Anthropic(", "messages.create"):
            if needle in text:
                offenders.append(f"{rel}: {needle}")
    assert not offenders, "Claude calls must go through llm/client.py:\n" + "\n".join(offenders)
