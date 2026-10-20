"""Library endpoints. A source is identified by its source_id: titles are not
unique (one production library has 21 sources with an empty title)."""

import pytest

from memory.source_store import typed_text

USER, OTHER = "user-a", "user-b"


@pytest.fixture
def a_headers(client, production, auth_headers):
    return auth_headers(USER)


@pytest.fixture
def ingestion(claude):
    """Every ingestion call (tags, context, entities, summary) answers with an empty list."""
    claude.respond_with(lambda kwargs: "[]")


def _ingest(text, title, user_id=USER):
    """Store a note through the real ingest path; returns its source_id."""
    from agents.ingestion_agent import ingest_content
    from db.supabase_client import supabase

    def ids():
        return {r["source_id"] for r in supabase.table("sources").select("source_id").eq("user_id", user_id)
                .execute().data}
    before = ids()
    ingest_content(text, source_type="note", source_title=title, user_id=user_id,
                   original=typed_text(text=text, title_provided=bool(title)))
    return (ids() - before).pop()


def _delete(client, headers, source_id):
    return client.request("DELETE", "/library/source", headers=headers, json={"source_id": source_id})


def _source_ids(fake_db, user_id=USER):
    return {r["source_id"] for r in fake_db.tables.get("sources", []) if r["user_id"] == user_id}


def _chunk_sources(fake_db, user_id=USER):
    return {r["source_id"] for r in fake_db.tables.get("embeddings", []) if r["user_id"] == user_id}


def test_deleting_a_source_removes_it_and_reports_its_chunk_count(client, a_headers, fake_db, ingestion):
    sid = _ingest("Notes on our billing rebuild.", "Notes")
    resp = _delete(client, a_headers, sid)

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "chunks_removed": 1, "message": "Removed 1 chunk"}
    assert _source_ids(fake_db) == set() and _chunk_sources(fake_db) == set()


@pytest.mark.parametrize("title", ["Notes", ""])
def test_deleting_one_of_two_same_title_sources_keeps_the_other(client, a_headers, fake_db, ingestion, title):
    """"" is the production case: images and backfilled sources with no title."""
    first = _ingest("First note about billing.", title)
    second = _ingest("Second note, about hiring.", title)

    assert _delete(client, a_headers, first).status_code == 200
    assert _source_ids(fake_db) == {second} and _chunk_sources(fake_db) == {second}
    assert [s["source_id"] for s in client.get("/library", headers=a_headers).json()["sources"]] == [second]


def test_unknown_or_another_users_source_id_is_404_and_deletes_nothing(client, a_headers, fake_db, ingestion):
    theirs = _ingest("Their note.", "Notes", user_id=OTHER)
    mine = _ingest("My note.", "Notes")

    assert _delete(client, a_headers, theirs).status_code == 404
    assert _delete(client, a_headers, "no-such-source").status_code == 404
    assert _source_ids(fake_db, OTHER) == {theirs} and _source_ids(fake_db) == {mine}


@pytest.mark.parametrize("body", [{"source_title": "Notes"}, {"source_id": ""}, {}])
def test_a_request_without_a_source_id_is_rejected(client, a_headers, fake_db, ingestion, body):
    """The pre-change frontend sends {source_title}: refused, nothing deleted."""
    _ingest("My note.", "Notes")
    resp = client.request("DELETE", "/library/source", headers=a_headers, json=body)
    assert resp.status_code == 422
    assert len(_source_ids(fake_db)) == 1


def test_library_lists_sources_not_consolidation_briefs(client, a_headers, fake_db, ingestion):
    from memory.consolidation_store import upsert_consolidation_chunk
    sid = _ingest("Notes on Kafka.", "Kafka notes")
    upsert_consolidation_chunk(USER, "ent-1", "kafka", "Everything about kafka.")

    sources = client.get("/library", headers=a_headers).json()["sources"]
    assert [s["source_id"] for s in sources] == [sid]


def test_clusters_identify_sources_by_id(client, a_headers, fake_db, claude):
    claude.respond_with(lambda kwargs: '["billing"]')            # every note gets the same tag
    ids = {_ingest("One note about billing.", "Notes"), _ingest("Another note about billing.", "Notes")}

    clusters = client.get("/library/clusters", headers=a_headers).json()["clusters"]
    assert {s["source_id"] for c in clusters for s in c["sources"]} == ids


def test_same_title_sources_show_their_own_retrieval_counts(client, a_headers, fake_db, ingestion):
    from memory.retrieval_stats_store import record_retrievals
    first = _ingest("First note about billing.", "")
    second = _ingest("Second note, about hiring.", "")
    record_retrievals(USER, [first])
    record_retrievals(USER, [first, second])

    counts = {s["source_id"]: s["retrieval_count"] for s in client.get("/library", headers=a_headers).json()["sources"]}
    assert counts == {first: 2, second: 1}


def test_library_shows_each_sources_authorship_and_who_set_it(client, a_headers, fake_db, ingestion):
    """Classifier and user labels come through; an unanswered source is NULL (the user is asked)."""
    mine, theirs, unanswered = _ingest("My note.", "A"), _ingest("An article.", "B"), _ingest("Unsure.", "C")
    _ingest("Another user's note.", "D", user_id=OTHER)
    labels = {mine: ("user_authored", "user"), theirs: ("external", "classifier")}
    for row in fake_db.tables["sources"]:
        if row["source_id"] in labels:
            row["authorship"], row["authorship_set_by"] = labels[row["source_id"]]

    got = {s["source_id"]: (s["authorship"], s["authorship_set_by"])
           for s in client.get("/library", headers=a_headers).json()["sources"]}
    assert got == {**labels, unanswered: (None, None)}


def test_a_source_with_no_sources_row_is_unlabelled(client, a_headers, fake_db, ingestion):
    """Legacy chunks written before migration 014 have no sources row."""
    sid = _ingest("Old note.", "Old")
    fake_db.tables["sources"] = [r for r in fake_db.tables["sources"] if r["source_id"] != sid]

    [source] = client.get("/library", headers=a_headers).json()["sources"]
    assert (source["authorship"], source["authorship_set_by"]) == (None, None)
