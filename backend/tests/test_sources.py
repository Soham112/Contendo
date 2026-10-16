"""Originals in `sources` and the source-originals bucket (memory/source_store.py)."""
import base64
from datetime import datetime, timedelta, timezone

import pytest

from memory import source_store
from memory.source_store import BUCKET, SourceOriginal, typed_text

USER = "user-a"
NOTE = "Notes from rebuilding our billing pipeline in the spring. " * 30


@pytest.fixture
def ingestion(claude):
    """Every ingestion call (tags, context, entities, summary) answers with an empty list."""
    claude.respond_with(lambda kwargs: "[]")


@pytest.fixture
def headers(client, production, auth_headers):
    return auth_headers(USER)


def _ingest(text=NOTE, original=None, **kw):
    from agents.ingestion_agent import ingest_content
    return ingest_content(text, source_type="note", user_id=kw.pop("user_id", USER),
                          original=original or typed_text(text=text, title_provided=False), **kw)


def _sources(fake_db, user_id=USER):
    return [r for r in fake_db.tables.get("sources", []) if r["user_id"] == user_id]


# --- write path ------------------------------------------------------------------

def test_typed_note_is_stored_verbatim_and_ready(fake_db, ingestion):
    original = "  First line\n\n" + NOTE
    _ingest(original, typed_text(text=original, title_provided=True))
    [row] = _sources(fake_db)
    assert row["status"] == "ready"
    assert row["raw_text"] == original and row["extracted_text"] == original
    assert (row["input_type"], row["extractor"], row["origin_status"]) == ("note", "verbatim", "original")
    assert row["title_origin"] == "provided"
    assert row["authorship"] is None and row["rebuild_check"] is None
    assert {r["source_id"] for r in fake_db.tables["embeddings"]} == {row["source_id"]}


def test_binary_original_goes_to_the_bucket_under_the_users_folder(fake_db, ingestion):
    data = b"%PDF-1.4 fake bytes"
    original = source_store.uploaded("file", data=data, mime="application/pdf",
                                     extractor=("file_extractor.pdf", "1"), title_provided=True,
                                     filename="Q3 plan.PDF")
    _ingest(NOTE, original)
    [row] = _sources(fake_db)
    assert row["raw_storage_path"].startswith(f"{USER}/{row['source_id']}/")
    assert row["raw_storage_path"].endswith(".pdf")
    assert row["raw_size_bytes"] == len(data) and row["raw_text"] is None
    assert fake_db.objects[(BUCKET, row["raw_storage_path"])] == data


def test_failed_upload_leaves_no_row_and_no_chunks(fake_db, ingestion):
    fake_db.fail_uploads = True
    original = source_store.uploaded("image", data=b"png", mime="image/png",
                                     extractor=("vision_agent", "1"), title_provided=False)
    with pytest.raises(RuntimeError):
        _ingest(NOTE, original)
    assert _sources(fake_db) == [] and fake_db.tables.get("embeddings", []) == []


def test_failed_chunk_write_removes_row_and_object(fake_db, ingestion, monkeypatch):
    import agents.ingestion_agent as agent

    def boom(*a, **k):
        raise RuntimeError("embeddings down")
    monkeypatch.setattr(agent, "upsert_chunks", boom)
    original = source_store.uploaded("image", data=b"png", mime="image/png",
                                     extractor=("vision_agent", "1"), title_provided=False)
    with pytest.raises(RuntimeError):
        _ingest(NOTE, original)
    assert _sources(fake_db) == [] and fake_db.objects == {}


def test_duplicate_content_writes_no_second_row(fake_db, ingestion):
    _ingest()
    assert _ingest().get("duplicate") is True
    assert len(_sources(fake_db)) == 1


def test_oversized_binaries_and_pages_are_recorded_as_omitted():
    big = source_store.uploaded("file", data=b"x" * (source_store.MAX_RAW_BYTES + 1), mime="text/plain",
                                extractor=("file_extractor.txt", "1"), title_provided=True)
    assert big.raw_bytes is None and big.raw_omitted_reason
    page = source_store.fetched_page(url="https://e.com", raw_markdown="é" * (source_store.MAX_PAGE_BYTES // 2 + 1),
                                     fetched_at="2026-10-15T00:00:00+00:00", extractor=("jina_reader", "1"),
                                     title_provided=True)
    assert page.raw_text is None and page.raw_omitted_reason


@pytest.mark.parametrize("kwargs", [
    {"input_type": "fax"},
    {"authorship": "user_authored"},                        # without who set it
    {"authorship": "mine", "authorship_set_by": "user"},
])
def test_invalid_originals_are_refused(kwargs):
    with pytest.raises(ValueError):
        SourceOriginal(**{"input_type": "note", "extractor": "verbatim", "extractor_version": "1", **kwargs})


# --- crash recovery ------------------------------------------------------------------

def test_sweep_removes_only_stale_pending_sources(fake_db):
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    old = (now - timedelta(hours=2)).isoformat()
    fresh = (now - timedelta(minutes=5)).isoformat()
    fake_db.tables["sources"] = [
        {"source_id": "crashed", "user_id": USER, "status": "pending", "updated_at": old,
         "raw_storage_path": f"{USER}/crashed/a.pdf"},
        {"source_id": "in-flight", "user_id": USER, "status": "pending", "updated_at": fresh},
        {"source_id": "done", "user_id": "user-b", "status": "ready", "updated_at": old},
    ]
    fake_db.tables["embeddings"] = [{"id": "crashed_0", "user_id": USER, "source_id": "crashed"},
                                    {"id": "done_0", "user_id": "user-b", "source_id": "done"}]
    fake_db.objects[(BUCKET, f"{USER}/crashed/a.pdf")] = b"pdf"

    assert source_store.sweep_stale_pending(now) == 1
    assert {r["source_id"] for r in fake_db.tables["sources"]} == {"in-flight", "done"}
    assert [r["id"] for r in fake_db.tables["embeddings"]] == ["done_0"]
    assert fake_db.objects == {}


# --- deletion ----------------------------------------------------------------------------

def test_library_delete_removes_row_object_and_chunks(client, headers, fake_db, ingestion):
    original = source_store.uploaded("file", data=b"bytes", mime="text/plain",
                                     extractor=("file_extractor.txt", "1"), title_provided=True)
    _ingest(NOTE, original, source_title="Billing notes")
    resp = client.request("DELETE", "/library/source", headers=headers, json={"source_title": "Billing notes"})
    assert resp.status_code == 200
    assert _sources(fake_db) == [] and fake_db.objects == {} and fake_db.tables["embeddings"] == []


def test_admin_deletes_one_users_sources_only(client, production, auth_headers, fake_db, ingestion):
    from tests.conftest import TEST_ADMIN_USER_ID
    for user in (USER, "user-b"):
        _ingest(NOTE + user, source_store.uploaded("image", data=user.encode(), mime="image/png",
                                                   extractor=("vision_agent", "1"), title_provided=False),
                user_id=user)
    url = f"/admin/users/{USER}/sources"
    assert client.delete(url, headers=auth_headers(USER)).status_code == 403
    resp = client.delete(url, headers=auth_headers(TEST_ADMIN_USER_ID))
    assert resp.json()["sources_removed"] == 1
    assert _sources(fake_db) == [] and len(_sources(fake_db, "user-b")) == 1
    assert [k[1].split("/")[0] for k in fake_db.objects] == ["user-b"]
    assert {r["user_id"] for r in fake_db.tables["embeddings"]} == {"user-b"}


# --- routes record their originals ------------------------------------------------

def test_file_upload_keeps_the_file(client, headers, fake_db, ingestion):
    data = NOTE.encode()
    resp = client.post("/ingest-file", headers=headers, files={"file": ("plan.txt", data, "text/plain")})
    assert resp.status_code == 200
    [row] = _sources(fake_db)
    assert (row["input_type"], row["extractor"], row["original_filename"]) == ("file", "file_extractor.txt", "plan.txt")
    assert fake_db.objects[(BUCKET, row["raw_storage_path"])] == data


def test_scrape_keeps_the_readers_unprocessed_response(client, headers, fake_db, ingestion, monkeypatch):
    import routers.ingest as ingest_router
    raw = "# Pricing lessons\n\nNav\n" + NOTE
    monkeypatch.setattr(ingest_router, "scrape_url", lambda url: {
        "content": NOTE, "title": "Pricing lessons", "word_count": 1, "source_url": url,
        "raw_markdown": raw, "fetched_at": "2026-10-15T10:00:00+00:00"})
    assert client.post("/scrape-and-ingest", headers=headers, json={"url": "https://e.com/p"}).status_code == 200
    [row] = _sources(fake_db)
    assert (row["input_type"], row["extractor"], row["raw_text"]) == ("url", "jina_reader", raw)
    assert row["extracted_text"] == NOTE and row["source_url"] == "https://e.com/p"
    assert row["fetched_at"] == "2026-10-15T10:00:00+00:00" and row["title_origin"] == "provided"


def test_image_keeps_the_decoded_bytes(client, headers, fake_db, ingestion, monkeypatch):
    import routers.ingest as ingest_router
    monkeypatch.setattr(ingest_router, "extract_from_image", lambda *a, **k: NOTE)
    data = b"\x89PNG fake"
    image = "data:image/png;base64," + base64.b64encode(data).decode()
    assert client.post("/ingest", headers=headers, json={"source_type": "image", "raw_image": image}).status_code == 200
    [row] = _sources(fake_db)
    assert (row["input_type"], row["raw_mime"], row["title_origin"]) == ("image", "image/png", "derived")
    assert fake_db.objects[(BUCKET, row["raw_storage_path"])] == data


def test_invalid_image_base64_is_a_400_before_any_model_call(client, headers, claude):
    resp = client.post("/ingest", headers=headers, json={"source_type": "image", "raw_image": "data:image/png;base64,@@@"})
    assert resp.status_code == 400 and claude.calls == []
