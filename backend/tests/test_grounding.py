"""Real semantic gate integration with explicitly queued model replies."""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from tests.generation_fixtures import make_state
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
    assert fake_db.tables["generation_traces"][0]["node_outputs"]["grounding"]["outcome"] == "needs_review"
