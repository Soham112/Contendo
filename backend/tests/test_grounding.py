"""No semantic grounding pass on the generation path (removed 2026-10-15): the
cited draft and the deterministic checks are the protection; a post is
returned without a second model reviewing or rewriting it."""
import pytest

from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)


@pytest.mark.parametrize("variant", ["C", "C-Opus"])
def test_a_draft_is_returned_without_a_grounding_check_or_repair(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import run_pipeline
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped
    from tests.test_generation_trace import USER

    claude.queue(ARCHETYPE_GENERAL, enveloped("We sold the home to a young couple. [[R]]"))
    result = run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER, variant=variant,
                          context="We sold the home to a couple.")

    assert result["status"] == "ok" and result["post"] == "We sold the home to a young couple."
    assert "grounding" not in result
    [trace] = fake_db.tables["generation_traces"]
    assert [call["event_type"] for call in trace["llm_calls"]] == ["archetype", "generate"]
    assert "grounding" not in trace["node_outputs"]
    # The deterministic checks still ran and were recorded.
    assert "checks_final" in trace["node_outputs"]


def test_generate_responds_without_a_grounding_field(client, claude, fake_db, seeded_kb, auth_headers):
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped
    from tests.test_generation_trace import USER

    claude.queue(ARCHETYPE_GENERAL, enveloped("pgvector makes retrieval fast. [[R]]"))
    response = client.post("/generate", headers=auth_headers(USER),
                           json={"topic": "pgvector makes retrieval fast", "format": "linkedin post", "tone": "casual"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok" and "grounding" not in response.json()
    assert len(claude.calls) == 2
