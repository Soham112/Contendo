"""The platform writes LinkedIn posts only (2026-10-15): ideas, /generate and
onboarding never produce a Medium article or a thread, whatever is asked."""
import json

import pytest


def test_every_parsed_idea_is_a_linkedin_post_whatever_the_model_says():
    from agents.ideation_agent import _parse_ideas

    raw = json.dumps([
        {"title": "A", "angle": "a", "frame": "observed_pattern", "reasoning": "r"},
        {"title": "B", "angle": "b", "format": "medium article", "frame": "forward_prediction", "reasoning": "r"},
        {"title": "C", "angle": "c", "format": "thread", "frame": "contrarian_take", "reasoning": "r"},
    ])

    ideas = _parse_ideas(raw, 3)

    assert [idea["title"] for idea in ideas] == ["A", "B", "C"]
    assert {idea["format"] for idea in ideas} == {"linkedin post"}


@pytest.mark.parametrize("name", ["SYSTEM_PROMPT", "RESUME_SYSTEM_PROMPT"])
def test_the_idea_prompts_ask_for_linkedin_posts_and_offer_no_other_format(name):
    import agents.ideation_agent as ideation

    prompt = getattr(ideation, name).lower()
    assert "linkedin post ideas" in prompt
    assert "medium" not in prompt and "thread" not in prompt and '"format"' not in prompt


@pytest.mark.parametrize("asked", ["medium article", "thread", "linkedin", "linkedin post"])
def test_generate_always_writes_a_linkedin_post(client, auth_headers, monkeypatch, asked):
    import routers.generate as generate

    seen: dict = {}

    def pipeline(**kwargs):
        seen.update(kwargs)
        return {"status": "ok", "post": "A post.", "score": 0, "score_feedback": [], "iterations": 1}

    monkeypatch.setattr(generate, "run_pipeline", pipeline)
    response = client.post("/generate", headers=auth_headers("user-a"),
                           json={"topic": "pgvector", "format": asked, "tone": "casual"})

    assert response.status_code == 200
    assert seen["format"] == "linkedin post"


def test_generate_needs_no_format_at_all(client, auth_headers, monkeypatch):
    import routers.generate as generate

    seen: dict = {}
    monkeypatch.setattr(generate, "run_pipeline", lambda **kwargs: seen.update(kwargs) or {
        "status": "ok", "post": "A post.", "score": 0, "score_feedback": [], "iterations": 1})
    response = client.post("/generate", headers=auth_headers("user-a"), json={"topic": "pgvector", "tone": "casual"})

    assert response.status_code == 200 and seen["format"] == "linkedin post"


def test_the_onboarding_brief_has_no_format_choice():
    from routers.onboarding import Brief

    assert "format" not in Brief.model_fields
