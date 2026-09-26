"""Library endpoints."""

import pytest


@pytest.fixture
def a_headers(client, production, auth_headers):
    return auth_headers("user-a")


def test_deleting_a_source_removes_its_chunks(client, a_headers, fake_db):
    from memory.vector_store import upsert_chunks

    upsert_chunks(["chunk one", "chunk two"], source_title="Notes", user_id="user-a")
    resp = client.request("DELETE", "/library/source", headers=a_headers, json={"source_title": "Notes"})

    assert resp.status_code == 200
    assert fake_db.tables["embeddings"] == []


def test_deleting_a_missing_source_returns_404(client, a_headers):
    resp = client.request("DELETE", "/library/source", headers=a_headers, json={"source_title": "Nope"})
    assert resp.status_code == 404


def test_delete_response_reports_chunk_count(client, a_headers):
    from memory.vector_store import upsert_chunks

    upsert_chunks(["chunk one", "chunk two"], source_title="Notes", user_id="user-a")
    resp = client.request("DELETE", "/library/source", headers=a_headers, json={"source_title": "Notes"})
    assert resp.status_code == 200
    assert resp.json() == {
        "deleted": True,
        "chunks_removed": 2,
        "message": "Removed 2 chunks",
    }
