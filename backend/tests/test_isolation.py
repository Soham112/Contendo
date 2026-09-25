"""One user must never read, change, or delete another user's data."""

import pytest

A, B = "user-a", "user-b"


def _log_post(client, headers, content="A's post about retrieval"):
    resp = client.post("/log-post", headers=headers, json={
        "topic": "retrieval", "format": "linkedin post", "tone": "casual",
        "content": content, "authenticity_score": 80,
    })
    assert resp.status_code == 200
    return resp.json()["post_id"]


@pytest.fixture
def api(client, production, auth_headers):
    """Client in production auth mode plus headers for users A and B."""
    return client, auth_headers(A), auth_headers(B)


# --- Posts and versions ------------------------------------------------------

def test_history_only_lists_own_posts(api):
    client, a, b = api
    _log_post(client, a)

    assert len(client.get("/history", headers=a).json()["posts"]) == 1
    assert client.get("/history", headers=b).json()["posts"] == []


def test_cannot_edit_another_users_post(api, fake_db):
    client, a, b = api
    post_id = _log_post(client, a, content="original")

    resp = client.patch(f"/history/{post_id}", headers=b, json={"content": "hijacked"})
    assert resp.json() == {"updated": False}

    post = next(p for p in fake_db.tables["posts"] if p["id"] == post_id)
    assert post["content"] == "original"
    assert all(v["content"] != "hijacked" for v in fake_db.tables["post_versions"])


def test_cannot_delete_another_users_post(api, fake_db):
    client, a, b = api
    post_id = _log_post(client, a)

    assert client.delete(f"/history/{post_id}", headers=b).status_code == 404
    assert any(p["id"] == post_id for p in fake_db.tables["posts"])


def test_cannot_publish_another_users_post(api):
    client, a, b = api
    post_id = _log_post(client, a)

    resp = client.patch(f"/history/{post_id}/publish", headers=b, json={"platform": "linkedin"})
    assert resp.status_code == 404


def test_cannot_restore_version_of_another_users_post(api, fake_db):
    client, a, b = api
    post_id = _log_post(client, a)
    version_id = fake_db.tables["post_versions"][0]["id"]

    resp = client.post(f"/history/{post_id}/restore/{version_id}", headers=b)
    assert resp.status_code == 404


# --- Profile ----------------------------------------------------------------

def test_profile_is_per_user(api):
    client, a, b = api
    client.post("/profile", headers=a, json={"name": "Alice", "role": "Data Scientist"})

    assert client.get("/profile", headers=a).json()["profile"]["name"] == "Alice"
    assert client.get("/profile", headers=b).json()["profile"]["name"] == ""


# --- Knowledge base ------------------------------------------------------------

def _seed_chunks(user_id, title, chunks):
    from memory.vector_store import upsert_chunks

    upsert_chunks(chunks, source_type="article", source_title=title, user_id=user_id)


def test_library_only_lists_own_sources(api):
    client, a, b = api
    _seed_chunks(A, "A's notes", ["vector databases and retrieval"])

    assert client.get("/library", headers=a).json()["sources"]
    assert client.get("/library", headers=b).json()["sources"] == []


def test_cannot_delete_another_users_source(api, fake_db):
    client, a, b = api
    _seed_chunks(A, "A's notes", ["vector databases and retrieval"])

    client.request("DELETE", "/library/source", headers=b, json={"source_title": "A's notes"})
    assert len([r for r in fake_db.tables["embeddings"] if r["user_id"] == A]) == 1


def test_vector_search_never_returns_another_users_chunks():
    from memory.vector_store import query_similar

    _seed_chunks(A, "A's notes", ["retrieval augmented generation with pgvector"])
    _seed_chunks(B, "B's notes", ["sourdough baking schedule"])

    query = "retrieval augmented generation pgvector"
    assert query_similar(query, user_id=A)[0]["source_title"] == "A's notes"  # search works
    results = query_similar(query, user_id=B)
    assert results and all(r["source_title"] == "B's notes" for r in results)


def test_hybrid_search_never_returns_another_users_chunks():
    from memory.vector_store import query_similar_hybrid

    _seed_chunks(A, "A's notes", ["retrieval augmented generation with pgvector"])
    _seed_chunks(B, "B's notes", ["sourdough baking schedule"])

    query = "retrieval augmented generation pgvector"
    assert query_similar_hybrid(query, user_id=A)[0]["source_title"] == "A's notes"  # search works
    results = query_similar_hybrid(query, user_id=B)
    assert results and all(r["source_title"] == "B's notes" for r in results)
