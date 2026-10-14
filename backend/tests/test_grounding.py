"""Real semantic gate integration with explicitly queued model replies."""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from tests.generation_fixtures import make_state
from tests.test_generation_trace import seeded_kb  # noqa: F401
from utils.citations import strip_citations

pytestmark = pytest.mark.grounding_integration


def state(post):
    stripped = strip_citations(post + " [[S1]]")
    return make_state([{"text": "We sold the home to a couple. The listed price was $400,000.",
                        "source_type": "personal_note", "memory_context": "work"}],
                      current_draft=stripped.text, final_post=stripped.text,
                      citations=[s.as_dict() for s in stripped.spans])


def review(text="", reason="unsupported detail"):
    return json.dumps({"sentences": [{"sentence": 1, "unsupported": [{"text": text, "reason": reason}] if text else []}]})


@pytest.mark.parametrize("draft,bad,corrected", [
    ("We sold the home to a young couple.", "young", "We sold the home to a couple."),
    ("The home sold for $900,000.", "$900,000", "The listed price was $400,000."),
])
def test_repairs_unsupported_claims_and_rechecks_the_actual_result(claude, draft, bad, corrected):
    from pipeline.grounding import enforce_grounding
    claude.queue(review(bad), corrected + " [[S1]]", review())
    result = enforce_grounding(state(draft))
    assert result["final_post"] == corrected
    assert result["grounding"]["outcome"] == "verified"
    assert result["grounding"]["flags"] == [] and result["grounding"]["repairs"] == 1
    assert len(claude.calls) == 3
    assert corrected in claude.calls[-1]["messages"][0]["content"]


def test_two_repairs_are_bounded_and_return_remaining_flags(claude):
    from pipeline.grounding import enforce_grounding
    draft = "We sold the home to a young couple."
    claude.queue(review("young"), draft + " [[S1]]", review("young"), draft + " [[S1]]", review("young"))
    result = enforce_grounding(state(draft))
    assert result["final_post"] == draft
    assert result["grounding"]["outcome"] == "needs_review"
    assert result["grounding"]["flags"][0]["text"] == "young"
    assert result["grounding"]["repairs"] == 2 and len(claude.calls) == 5


def test_supported_couple_and_price_need_no_repair(claude):
    from pipeline.grounding import enforce_grounding
    claude.queue(review())
    result = enforce_grounding(state("The listed price was $400,000."))
    assert result["grounding"]["outcome"] == "verified" and len(claude.calls) == 1


def test_invalid_review_coverage_is_explicit_not_clean(claude):
    from pipeline.grounding import enforce_grounding
    claude.queue('{"sentences": []}')
    result = enforce_grounding(state("We sold the home to a couple."))
    assert result["grounding"]["outcome"] == "needs_review"
    assert result["grounding"]["flags"][-1]["id"] == "verification_unavailable"


def test_api_failure_keeps_draft_and_requires_manual_review(claude):
    from pipeline.grounding import enforce_grounding
    def failed(kwargs):
        request = httpx.Request("POST", "https://example.invalid")
        raise anthropic.APIConnectionError(request=request)
    claude.respond_with(failed)
    result = enforce_grounding(state("We sold the home to a young couple."))
    assert result["final_post"].endswith("young couple.")
    assert result["grounding"]["outcome"] == "needs_review"


@pytest.mark.parametrize("variant", ["A", "B", "C", "B-Opus", "C-Opus"])
def test_every_pipeline_returns_and_persists_flags_before_responding(claude, fake_db, monkeypatch, variant):
    import pipeline.graph as graph
    draft = "We sold the home to a young couple."
    completed = state(draft)
    monkeypatch.setitem(graph.PIPELINES, variant, SimpleNamespace(invoke=lambda initial: completed))
    claude.queue(review("young"), draft + " [[S1]]", review("young"), draft + " [[S1]]", review("young"))
    result = graph.run_pipeline("Just sold", "linkedin", "conversational", user_id=completed["user_id"], variant=variant)
    assert result["status"] == "needs_review" and result["grounding"]["flags"][0]["text"] == "young"
    assert result["review"]["outcome"] == "issues_remain"
    assert fake_db.tables["generation_traces"][0]["node_outputs"]["grounding"]["outcome"] == "needs_review"


def test_flagged_draft_consumes_quota_and_is_not_reported_as_clean(client, auth_headers, monkeypatch):
    import routers.generate as generate
    monkeypatch.setattr(generate, "run_pipeline", lambda **kwargs: {
        "status": "needs_review", "post": "A young couple bought it.", "score": 0,
        "score_feedback": [], "iterations": 1,
        "grounding": {"outcome": "needs_review", "flags": [{"id": "age", "text": "young", "reason": "Age absent", "sentence": "A young couple bought it."}], "repairs": 2},
    })
    monkeypatch.setattr(generate, "_release_generation", lambda *args: pytest.fail("A returned flagged draft must count against quota"))
    headers = auth_headers("user-a")
    response = client.post("/generate", headers=headers, json={"topic": "Just sold", "format": "linkedin", "tone": "casual"})
    assert response.status_code == 200 and response.json()["status"] == "needs_review"
    assert response.json()["grounding"]["flags"][0]["text"] == "young"
    assert client.get("/billing/entitlements", headers=headers).json()["generations_used"] == 1


@pytest.mark.parametrize("variant", ["C", "C-Opus"])
def test_real_draft_graph_is_checked_and_repaired_before_response(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import run_pipeline
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped
    from tests.test_generation_trace import USER
    claude.queue(ARCHETYPE_GENERAL, enveloped("We sold the home to a young couple. [[R]]"),
                 review("young"), "We sold the home to a couple. [[R]]", review())
    result = run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER, variant=variant,
                          context="We sold the home to a couple.")
    assert result["post"] == "We sold the home to a couple."
    assert result["grounding"]["outcome"] == "verified"
    [trace] = fake_db.tables["generation_traces"]
    assert [call["event_type"] for call in trace["llm_calls"]][-3:] == ["grounding_check", "grounding_repair", "grounding_check"]
    assert len(claude.calls) == 5


def test_real_a_pipeline_finishes_grounding_without_a_deferred_check(claude, fake_db, seeded_kb):
    from tests.test_generation_trace import STANDARD_RUN, _run
    claude.queue(*STANDARD_RUN, review())
    result = _run()
    assert result["grounding"]["outcome"] == "verified"
    assert result["fact_check_job"] is None
    [trace] = fake_db.tables["generation_traces"]
    assert trace["llm_calls"][-1]["event_type"] == "grounding_check"
    assert trace["node_outputs"]["fact_check"] == {}
