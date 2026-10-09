"""Missing source tracking has one actionable API error and reason codes."""
import uuid
import pytest
from tests.test_refine_selection import _body, _seed_trace

@pytest.mark.parametrize("reason", ["no_identifier", "trace_not_found", "structured_chunks_missing"])
def test_missing_sources_returns_explicit_reason_without_calling_model(client, auth_headers, fake_db, claude, caplog, reason):
    kwargs = {}
    if reason == "trace_not_found":
        kwargs["trace_id"] = str(uuid.uuid4())
    elif reason == "structured_chunks_missing":
        kwargs["trace_id"] = _seed_trace(fake_db)
        fake_db.tables["generation_traces"][-1]["retrieved"] = []
    with caplog.at_level("WARNING"):
        response = client.post("/refine-selection", headers=auth_headers("user-a"), json=_body(**kwargs))
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "refine_sources_missing", "reason": reason,
        "message": "This post has no saved source tracking. Regenerate it to refine with sources."}}
    assert reason in caplog.text
    assert claude.calls == []


def test_refine_generates_from_structured_attributed_chunks_and_voice_only(claude, fake_db):
    from agents.refine_agent import refine_selection
    trace_id = _seed_trace(fake_db)
    row = fake_db.tables["generation_traces"][-1]
    row["retrieved_context"] = "STALE_UNATTRIBUTED_CONTEXT"
    row["retrieved"][0].update({"authorship": "self", "source_type": "note", "source_title": "AUTO_TITLE_SENTINEL"})
    row["profile_snapshot"].update({"bio": "BIO_SENTINEL", "expertise": ["EXPERTISE_SENTINEL"], "opinions": ["OPINION_SENTINEL"]})
    def reflect(kwargs):
        prompt = kwargs["messages"][0]["content"]
        source = "structured" if row["retrieved"][0]["text"] in prompt else "stale"
        leaks = [s for s in ("STALE_UNATTRIBUTED_CONTEXT", "AUTO_TITLE_SENTINEL", "BIO_SENTINEL", "EXPERTISE_SENTINEL", "OPINION_SENTINEL") if s in prompt]
        source += " attributed" if "OWN EXPERIENCE:" in prompt else " unattributed"
        return source + (" leaks " + " ".join(leaks) if leaks else " clean")
    claude.respond_with(reflect)
    result = refine_selection("It was slow.", "Improve flow", "It was slow.", user_id="user-a", trace_id=trace_id)
    assert result["rewritten_text"] == "structured attributed clean"


@pytest.mark.parametrize("retrieved,no_specifics", [
    ([], False), (None, False), ([{"source_title": "old title"}], False),
    ([{"text": "   "}], False), ([], True),
])
def test_unusable_structured_chunks_never_fall_back_to_cached_context(client, auth_headers, fake_db, claude, retrieved, no_specifics):
    trace_id = _seed_trace(fake_db, no_specifics=no_specifics)
    fake_db.tables["generation_traces"][-1]["retrieved"] = retrieved
    response = client.post("/refine-selection", headers=auth_headers("user-a"), json=_body(trace_id=trace_id))
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "structured_chunks_missing"
    assert claude.calls == []


@pytest.mark.parametrize("field,value", [
    ("bio", "BIO_CONTENT_SENTINEL"),
    ("topics_of_expertise", ["EXPERTISE_CONTENT_SENTINEL"]),
    ("opinions", ["OPINION_CONTENT_SENTINEL"]),
])
def test_profile_content_cannot_drive_refine_output(claude, fake_db, field, value):
    from agents.refine_agent import refine_selection
    trace_id = _seed_trace(fake_db)
    fake_db.tables["generation_traces"][-1]["profile_snapshot"][field] = value
    from memory.profile_store import save_profile
    save_profile({"name": "Alice", field: value}, user_id="user-a")
    sentinel = value if isinstance(value, str) else value[0]
    claude.respond_with(lambda kwargs: "leaked content" if sentinel in kwargs["messages"][0]["content"] else "voice only")
    result = refine_selection("It was slow.", "Improve flow", "It was slow.", user_id="user-a", trace_id=trace_id)
    assert result["rewritten_text"] == "voice only"


def test_lookup_operational_error_is_safe_logged_and_retryable(client, auth_headers, claude, caplog, monkeypatch):
    import agents.refine_agent as refine
    def fail(**kwargs):
        raise RuntimeError("PRIVATE_QUERY_CONTENT_SENTINEL")
    monkeypatch.setattr(refine, "get_trace_sources", fail)
    with caplog.at_level("ERROR"):
        response = client.post("/refine-selection", headers=auth_headers("user-a"),
            json=_body(trace_id=str(uuid.uuid4())))
    assert response.status_code == 500
    assert "try again" in response.json()["detail"].lower()
    assert "regenerate" not in response.text.lower()
    assert "category=RuntimeError" in caplog.text
    assert "PRIVATE_QUERY_CONTENT_SENTINEL" not in caplog.text + response.text
    assert claude.calls == []
