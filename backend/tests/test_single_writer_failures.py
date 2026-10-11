"""Regression contracts for unusable single-writer generation and refinement."""

import pytest
from anthropic.types import TextBlock

from tests.conftest import ARCHETYPE_GENERAL
from tests.length_fixtures import KB_USER, _outputs
from tests.test_generation_trace import seeded_kb  # noqa: F401
from tests.test_models import _reply, _thinking_block
from tests.test_refine_cited import GOOD, SELECTION, post, refine, _refines  # noqa: F401
from tests.test_refine_selection import post_refine  # noqa: F401


@pytest.mark.parametrize("reply", ["<post></post>", "<post> \n </post>", _reply(_thinking_block()), _reply()])
def test_default_generate_rejects_empty_completed_output(client, auth_headers, claude, fake_db, seeded_kb, reply):
    claude.queue(ARCHETYPE_GENERAL, reply)
    response = client.post("/generate", headers=auth_headers(KB_USER), json={
        "topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft_empty" and body["post"] == ""
    assert _outputs(fake_db)["draft_empty"]["reason"] == "empty_output"
    assert len(claude.calls) == 2


def test_blank_cited_refine_retries_and_accepts_valid_reply(refine, claude, fake_db):
    claude.queue(" \n ", GOOD)
    body = refine().json()
    assert body["status"] == "ok" and body["rewritten_text"] == "Retrieval gets fast with pgvector."
    assert len(claude.calls) == 2
    assert _refines(fake_db)[0]["attempts"][0]["reason"] == "empty_output"


def test_two_blank_cited_refine_replies_revert_explicitly(refine, claude, fake_db):
    claude.queue("", " \n ")
    body = refine().json()
    assert body["status"] == "reverted" and body["rewritten_text"] == SELECTION
    assert "no rewrite" in body["message"].lower() and "kept" in body["message"].lower()
    [record] = _refines(fake_db)
    assert [a["reason"] for a in record["attempts"]] == ["empty_output", "empty_output"]
    assert len(claude.calls) == 2


@pytest.mark.parametrize("model,reason", [(None, "draft_model_missing"), ("unrecognised-model", "draft_model_unknown")])
def test_cited_refine_rejects_unresolvable_saved_model(refine, claude, fake_db, model, reason):
    outputs = _outputs(fake_db)
    if model is None:
        outputs["models"].pop("draft")
    else:
        outputs["models"]["draft"] = model
    response = refine()
    assert response.status_code == 409 and response.json()["detail"]["reason"] == reason
    assert claude.calls == []


@pytest.mark.parametrize("retry,expected", [(GOOD, "ok"), ("Both sources support retrieval. [[S1,S2]]", "reverted")])
def test_mixed_citations_trigger_retry_and_revert_if_repeated(refine, claude, fake_db, retry, expected):
    [trace] = fake_db.tables["generation_traces"]
    trace["retrieved"].append({"text": "Both sources support retrieval.", "source_type": "note"})
    index = trace["node_outputs"]["source_index"]
    index["S1"]["authorship"] = "external"
    index["S2"] = {**index["S1"], "position": 1, "authorship": "self"}
    claude.queue("Both sources support retrieval. [[S1,S2]]", retry)
    body = refine().json()
    assert body["status"] == expected and len(claude.calls) == 2
    assert "mixed_authorship_span" in _refines(fake_db)[0]["attempts"][0]["checks"]["counts"]
    if expected == "reverted":
        assert body["rewritten_text"] == SELECTION and body["message"]


def test_old_refine_reads_text_after_thinking(post_refine, claude):
    claude.queue(_reply(_thinking_block(), TextBlock(type="text", text="It crawled at first.")))
    body = post_refine().json()
    assert body["status"] == "ok" and body["rewritten_text"] == "It crawled at first."


@pytest.mark.parametrize("stop_reason,says", [("refusal", "declined"), ("max_tokens", "cut off")])
def test_old_refine_reverts_refusal_and_truncation_without_retry(post_refine, claude, stop_reason, says):
    claude.queue(_reply(TextBlock(type="text", text="An unfinished rewrite"), stop_reason=stop_reason))
    body = post_refine().json()
    assert body["status"] == "reverted" and body["rewritten_text"] == "It was slow at first."
    assert says in body["message"] and len(claude.calls) == 1
