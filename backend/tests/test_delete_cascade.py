"""Delete cascade (memory/derived_store.py, migration 016) and replace-in-place
(memory/source_store.py begin_replace): what goes with a deleted chunk or source,
and a replace that fails or crashes partway leaves the old content intact."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from memory import source_store
from memory.source_store import BUCKET, typed_text

USER, OTHER = "user-a", "user-b"
ENTITY_WORDS = ("kafka", "stripe", "postgres", "redis")


def _respond(kwargs):
    """Entity extraction names every ENTITY_WORDS word in the chunk; any other
    ingestion call (tags, context, summary, consolidation) answers "[]"."""
    if str(kwargs.get("system", "")).startswith("You are an entity extraction"):
        text = str(kwargs["messages"][-1]["content"]).lower()
        return json.dumps([{"entity_name": w, "entity_type": "technology", "relationship_type": "mentions"}
                           for w in ENTITY_WORDS if w in text])
    return "[]"


@pytest.fixture
def ingestion(claude):
    claude.respond_with(_respond)


def _text(seed: str, *markers: str) -> str:
    """A note with one chunk per marker: chunks are 500 words with 50 overlap, so
    a word at 450*i + 200 is in chunk i only."""
    words = [f"{seed}{n}" for n in range(450 * (len(markers) - 1) + 500)]
    for i, marker in enumerate(markers):
        words[450 * i + 200] = marker
    return " ".join(words)


def _source_ids(user_id=USER):
    from db.supabase_client import supabase
    return {r["source_id"] for r in supabase.table("sources").select("source_id").eq("user_id", user_id)
            .execute().data}


def _ingest(text, *, user_id=USER, title=None, replace=None, original=None):
    """Returns the source_id written (the replaced one, or the new one)."""
    from agents.ingestion_agent import ingest_content
    before = _source_ids(user_id)
    ingest_content(text, source_type="note", user_id=user_id, source_title=title, replace_source_id=replace,
                   original=original or typed_text(text=text, title_provided=title is not None))
    return replace or (_source_ids(user_id) - before).pop()


def _rows(fake_db, table, user_id=USER):
    return [r for r in fake_db.tables.get(table, []) if r.get("user_id") == user_id]


def _chunk_ids(fake_db, source_id):
    return {r["id"] for r in fake_db.tables.get("embeddings", []) if r.get("source_id") == source_id}


def _entity_names(fake_db, user_id=USER):
    return {r["entity_name"] for r in _rows(fake_db, "entities", user_id)}


def _linked_names(fake_db, chunk_ids):
    names = {r["entity_id"]: r["entity_name"] for r in fake_db.tables.get("entities", [])}
    return {names[r["entity_id"]] for r in fake_db.tables.get("chunk_entities", []) if r["chunk_id"] in chunk_ids}


def _brief_entities(fake_db, user_id=USER):
    names = {r["entity_id"]: r["entity_name"] for r in fake_db.tables.get("entities", [])}
    return {names.get(r["source_id"], r["source_id"]) for r in _rows(fake_db, "embeddings", user_id)
            if r.get("node_type") == "consolidation"}


def _add_briefs(fake_db, *names):
    from memory.consolidation_store import upsert_consolidation_chunk
    for e in _rows(fake_db, "entities"):
        if e["entity_name"] in names:
            upsert_consolidation_chunk(USER, e["entity_id"], e["entity_name"], f"brief on {e['entity_name']}")


# --- deleting a source ------------------------------------------------------------------

def test_deleting_a_source_removes_its_links_unlinked_entities_and_affected_briefs(fake_db, ingestion):
    a = _ingest(_text("a", "kafka", "stripe"), title="A")
    b = _ingest(_text("b", "kafka"), title="B")
    c = _ingest(_text("c", "postgres"), title="C")
    _add_briefs(fake_db, "kafka", "stripe", "postgres")
    a_chunks, b_chunks = _chunk_ids(fake_db, a), _chunk_ids(fake_db, b)

    assert source_store.delete_sources([a], USER) == 1

    assert not [r for r in fake_db.tables["chunk_entities"] if r["chunk_id"] in a_chunks]
    assert _linked_names(fake_db, b_chunks) == {"kafka"}               # the other source's links stay
    assert _entity_names(fake_db) == {"kafka", "postgres"}             # stripe had no other chunk
    assert _brief_entities(fake_db) == {"postgres"}                    # kafka's brief held A's text
    assert _chunk_ids(fake_db, c) and _rows(fake_db, "sources")


def test_deleting_the_last_source_of_an_entity_removes_entity_and_brief(fake_db, ingestion):
    a = _ingest(_text("a", "redis"), title="A")
    _add_briefs(fake_db, "redis")
    source_store.delete_sources([a], USER)
    assert _entity_names(fake_db) == set() and _brief_entities(fake_db) == set()
    assert _rows(fake_db, "chunk_entities") == []


def test_delete_removes_hierarchy_rows_and_the_sources_own_retrieval_count(fake_db, ingestion):
    a = _ingest(_text("a", "kafka"), title="Shared")
    b = _ingest(_text("b", "kafka"), title="Shared")
    fake_db.tables["source_retrieval_stats"] = [{"user_id": USER, "source_id": sid, "retrieval_count": 4}
                                                for sid in (a, b)]
    assert {r["source_id"] for r in _rows(fake_db, "source_nodes")} == {a, b}

    source_store.delete_sources([a], USER)
    assert {r["source_id"] for r in _rows(fake_db, "source_nodes")} == {b}
    assert all(a not in t["child_source_ids"] for t in _rows(fake_db, "topic_nodes"))
    assert [r["source_id"] for r in _rows(fake_db, "source_retrieval_stats")] == [b]   # same title, own count


def test_library_delete_stops_keyword_search_returning_the_text(client, production, auth_headers, fake_db, ingestion):
    from memory.vector_store import _query_bm25
    airships = _ingest(_text("a", "zeppelin"), title="Airships")
    _ingest(_text("b", "kafka"), title="Queues")
    _ingest(_text("c", "postgres"), title="Databases")
    assert any("zeppelin" in r["text"] for r in _query_bm25("zeppelin", USER))   # index built and cached

    resp = client.request("DELETE", "/library/source", headers=auth_headers(USER), json={"source_id": airships})
    assert resp.status_code == 200
    assert not any("zeppelin" in r["text"] for r in _query_bm25("zeppelin", USER))


def test_admin_delete_leaves_nothing_derived_and_makes_no_model_call(client, production, auth_headers, fake_db,
                                                                     claude, ingestion):
    from tests.conftest import TEST_ADMIN_USER_ID
    _ingest(_text("a", "kafka"), title="A")
    _ingest(_text("b", "kafka"), title="B", user_id=OTHER)
    calls = len(claude.calls)

    resp = client.delete(f"/admin/users/{USER}/sources", headers=auth_headers(TEST_ADMIN_USER_ID))
    assert resp.status_code == 200 and len(claude.calls) == calls
    for table in ("sources", "embeddings", "chunk_entities", "entities", "source_nodes"):
        assert _rows(fake_db, table) == [], table
    assert all(not t["child_source_ids"] for t in _rows(fake_db, "topic_nodes"))
    assert _entity_names(fake_db, OTHER) == {"kafka"} and _rows(fake_db, "embeddings", OTHER)


def test_source_count_for_consolidation_comes_from_the_chunks_source_id(fake_db):
    from memory.entity_store import get_entities_with_source_count
    from memory.vector_store import upsert_chunks
    fake_db.tables["entities"] = [{"entity_id": "e1", "user_id": USER, "entity_name": "kafka", "entity_type": "technology"}]
    links = []
    for sid in ("s_1", "s_2", "s_3"):                                 # source ids with underscores
        upsert_chunks(["one", "two"], source_id=sid, user_id=USER, ingest_id="i1")
        links += [{"chunk_id": f"{sid}_i1_{i}", "entity_id": "e1", "user_id": USER,
                   "relationship_type": "mentions"} for i in (0, 1)]
    fake_db.tables["chunk_entities"] = links
    assert [r["source_count"] for r in get_entities_with_source_count(USER, min_sources=3)] == [3]
    assert get_entities_with_source_count(USER, min_sources=4) == []


# --- replacing a source in place -----------------------------------------------------------

@pytest.mark.parametrize("old_markers", [("kafka", "stripe", "postgres"), ("kafka",)])
def test_replace_leaves_no_stale_links(fake_db, ingestion, old_markers):
    """Fewer chunks, or the same number (the old ids were reused, so the new chunk
    inherited the old chunk's links)."""
    sid = _ingest(_text("old", *old_markers))
    old_chunks = _chunk_ids(fake_db, sid)

    _ingest(_text("new", "redis"), replace=sid)

    new_chunks = _chunk_ids(fake_db, sid)
    row = source_store.get_source(sid, USER)
    assert len(new_chunks) == 1 and not new_chunks & old_chunks
    assert {r["chunk_id"] for r in fake_db.tables["chunk_entities"]} == new_chunks
    assert _linked_names(fake_db, new_chunks) == {"redis"}
    assert _entity_names(fake_db) == {"redis"}
    assert row["extracted_text"].startswith("new0") and row["pending_replace"] is None
    assert {r["ingest_id"] for r in fake_db.tables["embeddings"]} == {row["ingest_id"]}


def _snapshot(fake_db):
    keep = ("embeddings", "chunk_entities", "entities")
    row = dict(_rows(fake_db, "sources")[0])
    row.pop("updated_at")
    row["pending_replace"] = row.get("pending_replace")   # absent before 016's column was written
    return {t: sorted(map(repr, fake_db.tables.get(t, []))) for t in keep}, row, dict(fake_db.objects)


def test_failure_mid_replace_keeps_the_old_note(fake_db, ingestion, monkeypatch):
    import agents.ingestion_agent as agent
    from memory.vector_store import upsert_chunks
    sid = _ingest(_text("old", "kafka", "stripe"))
    before = _snapshot(fake_db)

    def write_then_fail(*args, **kwargs):
        upsert_chunks(*args, **kwargs)                                # the new rows are written...
        raise RuntimeError("connection dropped")                      # ...then the write fails
    monkeypatch.setattr(agent, "upsert_chunks", write_then_fail)
    with pytest.raises(RuntimeError):
        _ingest(_text("new", "redis"), replace=sid)

    assert _snapshot(fake_db) == before


def test_failed_upload_mid_replace_keeps_the_old_original(fake_db, ingestion):
    def image(data):
        return source_store.uploaded("image", data=data, mime="image/png", extractor=("vision_agent", "1"),
                                     title_provided=False)
    from agents.ingestion_agent import ingest_content
    ingest_content(_text("old", "kafka"), source_type="note", user_id=USER, original=image(b"old"))
    [sid] = _source_ids()
    before = _snapshot(fake_db)

    fake_db.fail_uploads = True
    with pytest.raises(RuntimeError):
        ingest_content(_text("new", "redis"), source_type="note", user_id=USER,
                       original=image(b"new"), replace_source_id=sid)
    assert _snapshot(fake_db) == before


def test_successful_replace_swaps_the_original_object(fake_db, ingestion):
    from agents.ingestion_agent import ingest_content

    def image(data):
        return source_store.uploaded("image", data=data, mime="image/png", extractor=("vision_agent", "1"),
                                     title_provided=False)
    ingest_content(_text("old", "kafka"), source_type="note", user_id=USER, original=image(b"old"))
    [sid] = _source_ids()
    ingest_content(_text("new", "redis"), source_type="note", user_id=USER, original=image(b"new"),
                   replace_source_id=sid)
    assert list(fake_db.objects.values()) == [b"new"]
    assert (BUCKET, source_store.get_source(sid, USER)["raw_storage_path"]) in fake_db.objects


def _crash_mid_replace(fake_db, sid, *, switched: bool):
    """begin_replace and the chunk write ran; the process died before commit
    finished (switched: after the row moved to the new set)."""
    from memory.vector_store import upsert_chunks
    write = source_store.begin_replace(USER, sid, typed_text(text="new", title_provided=False),
                                       title="t", extracted_text="new", content_hash="h2", lang=None)
    upsert_chunks(["new text"], source_id=sid, user_id=USER, ingest_id=write.ingest_id)
    if switched:
        fake_db.tables["sources"][0]["ingest_id"] = write.ingest_id
    fake_db.tables["sources"][0]["updated_at"] = "2026-10-15T00:00:00+00:00"
    return write


@pytest.mark.parametrize("switched", [False, True])
def test_sweep_undoes_or_finishes_a_crashed_replace(fake_db, ingestion, switched):
    sid = _ingest(_text("old", "kafka"))
    old_chunks = _chunk_ids(fake_db, sid)
    write = _crash_mid_replace(fake_db, sid, switched=switched)

    assert source_store.sweep_stale_pending(datetime(2026, 10, 15, 12, tzinfo=timezone.utc)) == 1
    kept = {r["ingest_id"] for r in fake_db.tables["embeddings"]}
    assert kept == ({write.ingest_id} if switched else {source_store.get_source(sid, USER)["ingest_id"]})
    assert (_chunk_ids(fake_db, sid) == old_chunks) is not switched
    assert source_store.get_source(sid, USER)["pending_replace"] is None


def test_one_replace_at_a_time_and_a_crashed_one_does_not_block_the_next(fake_db, ingestion):
    sid = _ingest(_text("old", "kafka"))
    source_store.begin_replace(USER, sid, typed_text(text="x", title_provided=False),
                               title="t", extracted_text="x", content_hash="h2", lang=None)
    with pytest.raises(source_store.ReplaceInProgress):
        _ingest(_text("new", "redis"), replace=sid)

    fake_db.tables["sources"][0]["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _ingest(_text("new", "redis"), replace=sid)
    assert _linked_names(fake_db, _chunk_ids(fake_db, sid)) == {"redis"}
    assert source_store.get_source(sid, USER)["pending_replace"] is None


def test_profile_note_save_replaces_in_place_without_stale_links(client, production, auth_headers, fake_db,
                                                                  ingestion):
    """The account route's replace path, end to end: one sources row, one chunk
    set, no links from the previous note."""
    from routers.account import _save_profile_to_memory
    account = {"business_profile": {"business_name": "Kafka Plumbing", "services": "drains",
                                    "service_area": "Leeds"},
               "business_niche": "home_services", "business_niche_other": None}
    _save_profile_to_memory(account, USER)
    first = _rows(fake_db, "sources")
    account["business_profile"] = {**account["business_profile"], "business_name": "Redis Plumbing"}
    _save_profile_to_memory(account, USER)

    rows = _rows(fake_db, "sources")
    assert len(rows) == 1 and rows[0]["source_id"] == first[0]["source_id"]
    chunks = _chunk_ids(fake_db, rows[0]["source_id"])
    assert "kafka" not in _linked_names(fake_db, chunks) and "kafka" not in _entity_names(fake_db)
