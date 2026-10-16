"""Backfill of `sources` from stored chunks (scripts/backfill_sources.py, utils/source_rebuild.py)."""
import hashlib

import pytest

from scripts import backfill_sources as backfill
from utils.chunker import chunk_text
from utils.source_rebuild import rebuild_source

USER = "user-a"


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _words(n: int, start: int = 0) -> str:
    return " ".join(f"w{i}" for i in range(start, start + n))


def _rows(original: str, source_id: str = "s1", user_id: str = USER, **extra) -> list[dict]:
    """Chunk rows exactly as ingest stored them: chunker_v1 over the original."""
    chunks = chunk_text(original)
    return [{
        "user_id": user_id, "source_id": source_id, "content": c, "chunk_index": i,
        "total_chunks": len(chunks), "content_hash": _hash(original), "source_title": "T",
        "source_type": "note", "node_type": "chunk", "ingested_at": "2026-05-01T00:00:00+00:00", **extra,
    } for i, c in enumerate(chunks)]


# --- rebuild_source ------------------------------------------------------------

@pytest.mark.parametrize("n_words", [1, 499, 500, 501, 950, 1234, 2000])
def test_single_spaced_original_is_rebuilt_exactly_with_hash_match(n_words):
    original = _words(n_words)
    rebuilt = rebuild_source(_rows(original))
    assert rebuilt.text == original
    assert (rebuilt.check, rebuilt.hash_match) == ("rechunk_exact", True)


def test_line_breaks_are_lost_so_rechunk_matches_but_hash_does_not():
    original = "# Heading\n\n" + _words(700) + "\n\n  closing   line"
    rebuilt = rebuild_source(_rows(original))
    assert (rebuilt.check, rebuilt.hash_match) == ("rechunk_exact", False)
    assert rebuilt.text == " ".join(original.split())


def test_rows_in_any_order_rebuild_the_same():
    rows = _rows(_words(1600))
    assert rebuild_source(list(reversed(rows))).text == _words(1600)


def test_chunks_from_another_chunker_are_a_mismatch():
    # No overlap: dropping 50 words per chunk loses text, and rechunking disagrees.
    words = _words(1000).split()
    chunks = [" ".join(words[:500]), " ".join(words[500:])]
    rows = [{"content": c, "chunk_index": i, "total_chunks": 2, "content_hash": _hash(_words(1000))}
            for i, c in enumerate(chunks)]
    rebuilt = rebuild_source(rows)
    assert rebuilt.check == "rechunk_mismatch"
    assert rebuilt.hash_match is False


def test_edit_inside_the_overlap_is_a_mismatch():
    # w460 is in chunk 0's tail and chunk 1's head: the two copies now disagree.
    rows = _rows(_words(1200))
    rows[1]["content"] = rows[1]["content"].replace("w460", "edited")
    assert rebuild_source(rows).check == "rechunk_mismatch"


def test_edit_outside_the_overlap_is_caught_only_by_the_hash():
    # A consistent edit rebuilds and rechunks cleanly; the stored hash still differs.
    rows = _rows(_words(1200))
    rows[1]["content"] = rows[1]["content"].replace("w600", "edited")
    assert (rebuild_source(rows).check, rebuild_source(rows).hash_match) == ("rechunk_exact", False)


def test_missing_chunk_is_incomplete():
    rows = _rows(_words(1500))
    del rows[1]
    rebuilt = rebuild_source(rows)
    assert (rebuilt.check, rebuilt.hash_match) == ("incomplete", None)


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.append(dict(rows[0])),                  # duplicated index
    lambda rows: rows[0].update(total_chunks=9),              # rows disagree on the total
    lambda rows: [r.update(total_chunks=None) for r in rows],  # no total recorded
])
def test_inconsistent_indexes_are_incomplete(mutate):
    rows = _rows(_words(1200))
    mutate(rows)
    assert rebuild_source(rows).check == "incomplete"


def test_no_stored_hash_gives_no_hash_verdict():
    rows = _rows(_words(800))
    for r in rows:
        r["content_hash"] = ""
    rebuilt = rebuild_source(rows)
    assert (rebuilt.check, rebuilt.hash_match) == ("rechunk_exact", None)


# --- plan, report, apply -----------------------------------------------------------

def test_plan_marks_every_source_rebuilt_and_leaves_authorship_unknown():
    rows = (_rows(_words(900), "s1") + _rows("short note text", "s2", source_type="youtube")
            + _rows(_words(30), "s3", user_id="user-b", source_type="business_profile"))
    planned = {r["source_id"]: r for r in backfill.plan(rows)}
    assert set(planned) == {"s1", "s2", "s3"}
    for row in planned.values():
        assert row["origin_status"] == "rebuilt_from_chunks"
        assert row["status"] == "ready"
        assert row["extractor"] == "rebuilt_from_chunks"
        assert "authorship" not in row and "title_origin" not in row and "raw_text" not in row
    assert planned["s1"]["input_type"] == "unknown"  # 'note' may be typed text or Obsidian
    assert planned["s2"]["input_type"] == "youtube"
    assert planned["s3"]["input_type"] == "business_profile"
    assert planned["s3"]["user_id"] == "user-b"
    assert planned["s1"]["content_hash"] == _hash(_words(900))
    assert planned["s1"]["created_at"] == "2026-05-01T00:00:00+00:00"


def test_plan_skips_consolidation_rows():
    consolidation = {"user_id": USER, "source_id": "entity-1", "content": "synth", "chunk_index": 0,
                     "total_chunks": 1, "source_type": "consolidation", "node_type": "consolidation"}
    legacy = {**consolidation, "node_type": None}
    planned = backfill.plan(_rows("a note", "s1") + [consolidation, legacy])
    assert [r["source_id"] for r in planned] == ["s1"]


def test_duplicates_are_reported_per_user():
    text = _words(40)
    rows = _rows(text, "s1") + _rows(text, "s2") + _rows(text, "s3", user_id="user-b") + _rows("other", "s4")
    planned = backfill.plan(rows)
    assert backfill.duplicates(planned) == {USER: [["s1", "s2"]]}
    out = backfill.report(rows, planned, existing=set())
    assert "1 groups" in out and "user-a: s1, s2" in out
    assert text not in out  # no source text in the report


def test_apply_reads_past_the_page_limit_and_is_idempotent(fake_db, monkeypatch):
    monkeypatch.setattr(backfill, "PAGE", 3)
    rows = _rows(_words(2100), "big") + _rows("note one", "s1") + _rows("note two", "s2")
    fake_db.tables["embeddings"] = [{**r, "id": f"{r['source_id']}_{r['chunk_index']}"} for r in rows]

    fetched = backfill.fetch_chunk_rows(fake_db)
    assert len(fetched) == len(rows)
    planned = backfill.plan(fetched)
    assert backfill.apply(fake_db, planned, backfill.fetch_source_ids(fake_db)) == 3
    assert backfill.apply(fake_db, planned, backfill.fetch_source_ids(fake_db)) == 0
    stored = {r["source_id"]: r for r in fake_db.tables["sources"]}
    assert stored["big"]["extracted_text"] == _words(2100)
    assert stored["big"]["rebuild_check"] == "rechunk_exact"


def test_apply_on_production_needs_explicit_confirmation():
    with pytest.raises(SystemExit):
        backfill.main(["--target", "production", "--apply"])
