"""Originals of every ingested source: the `sources` table and the private
`source-originals` Storage bucket (migration 014).

Write order, so a crash can never leave an object or chunk nobody knows about:
  1. begin_source: the row, status 'pending' (names the object path and the
     ingest_id of the chunk set). begin_replace: the existing row records the
     new object path and ingest_id in `pending_replace`; its content stays live.
  2. the Storage object, if the original is binary
  3. the chunks (by the caller, vector_store.upsert_chunks with the ingest_id)
  4. SourceWrite.commit: a new row becomes 'ready'; a replaced row switches to
     the new content and ingest_id, then the old chunk set and object are
     deleted and pending_replace is cleared
A failure in 2-3 calls SourceWrite.abort inline (a new source is removed; a
replace removes only its new chunks and object). A crash leaves a pending row
or a pending_replace; sweep_stale_pending removes the row, or finishes the
replace (row already switched) or undoes it (not switched).
Deletes remove derived data too (memory/derived_store.py).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from db import id_batches
from db.supabase_client import supabase
from memory import derived_store
from memory.vector_store import new_ingest_id

logger = logging.getLogger(__name__)

BUCKET = "source-originals"
STALE_PENDING_AFTER = timedelta(minutes=30)
SWEEP_EVERY_SECONDS = 3600
MAX_RAW_BYTES = 10 * 1024 * 1024   # the bucket's file_size_limit (migration 014)
MAX_PAGE_BYTES = 5 * 1024 * 1024   # fetched page text kept per URL source
INPUT_TYPES = frozenset({"note", "file", "url", "youtube", "image", "obsidian", "business_profile"})
AUTHORSHIPS = frozenset({"user_authored", "user_stated", "external", "system_inferred"})
# Typed or pasted text is stored as received: there is no extraction step.
VERBATIM = ("verbatim", "1")


@dataclass(frozen=True)
class SourceOriginal:
    """What the user gave us and how its text was extracted. Built by each ingest route."""
    input_type: str
    extractor: str
    extractor_version: str
    raw_text: str | None = None
    raw_bytes: bytes | None = None
    raw_mime: str | None = None
    raw_json: dict | None = None
    raw_omitted_reason: str | None = None
    source_url: str | None = None
    original_filename: str | None = None
    fetched_at: str | None = None
    title_origin: str | None = None
    authorship: str | None = None
    authorship_set_by: str | None = None

    def __post_init__(self) -> None:
        if self.input_type not in INPUT_TYPES:
            raise ValueError(f"unknown input_type {self.input_type!r}")
        if self.authorship is not None and self.authorship not in AUTHORSHIPS:
            raise ValueError(f"unknown authorship {self.authorship!r}")
        if (self.authorship is None) != (self.authorship_set_by is None):
            raise ValueError("authorship and authorship_set_by are set together")


def typed_text(input_type: str = "note", *, text: str, title_provided: bool, **extra: Any) -> SourceOriginal:
    """Original for text received as is (typed, pasted, an Obsidian note's file text)."""
    return SourceOriginal(
        input_type=input_type, extractor=VERBATIM[0], extractor_version=VERBATIM[1],
        raw_text=text, title_origin="provided" if title_provided else "derived", **extra,
    )


def uploaded(input_type: str, *, data: bytes, mime: str, extractor: tuple[str, str],
             title_provided: bool, filename: str | None = None) -> SourceOriginal:
    """Original for an uploaded file or image: the bytes go to Storage."""
    too_large = len(data) > MAX_RAW_BYTES
    return SourceOriginal(
        input_type=input_type, extractor=extractor[0], extractor_version=extractor[1],
        raw_bytes=None if too_large else data, raw_mime=mime, original_filename=filename,
        raw_omitted_reason=f"over {MAX_RAW_BYTES} bytes" if too_large else None,
        title_origin="provided" if title_provided else "derived",
    )


def fetched_page(*, url: str, raw_markdown: str, fetched_at: str, extractor: tuple[str, str],
                 title_provided: bool) -> SourceOriginal:
    """Original for a scraped URL: the reader's unprocessed response, capped at MAX_PAGE_BYTES."""
    too_large = len(raw_markdown.encode()) > MAX_PAGE_BYTES
    return SourceOriginal(
        input_type="url", extractor=extractor[0], extractor_version=extractor[1],
        raw_text=None if too_large else raw_markdown, raw_mime="text/markdown",
        raw_omitted_reason=f"over {MAX_PAGE_BYTES} bytes" if too_large else None,
        source_url=url, fetched_at=fetched_at,
        title_origin="provided" if title_provided else "derived",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_path(user_id: str, source_id: str, original: SourceOriginal, sha256: str) -> str:
    ext = mimetypes.guess_extension(original.raw_mime or "") or ""
    if original.original_filename and "." in original.original_filename:
        ext = "." + original.original_filename.rsplit(".", 1)[1].lower()
    return f"{user_id}/{source_id}/{sha256}{ext}"


def _content_fields(user_id: str, source_id: str, original: SourceOriginal, *,
                    title: str, extracted_text: str, content_hash: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "status": "pending",
        "input_type": original.input_type,
        "title": title,
        "title_origin": original.title_origin,
        "source_url": original.source_url,
        "original_filename": original.original_filename,
        "fetched_at": original.fetched_at,
        "raw_text": original.raw_text,
        "raw_json": original.raw_json,
        "raw_storage_path": None,
        "raw_mime": original.raw_mime,
        "raw_size_bytes": None,
        "raw_sha256": None,
        "raw_omitted_reason": original.raw_omitted_reason,
        "extracted_text": extracted_text,
        "extractor": original.extractor,
        "extractor_version": original.extractor_version,
        "extracted_at": _now(),
        "content_hash": content_hash,
        "origin_status": "original",
        "rebuild_check": None,
        "rebuild_hash_match": None,
        "authorship": original.authorship,
        "authorship_set_by": original.authorship_set_by,
        "authorship_detail": None,
        "updated_at": _now(),
    }
    if original.raw_bytes is not None:
        sha = hashlib.sha256(original.raw_bytes).hexdigest()
        fields |= {
            "raw_storage_path": _storage_path(user_id, source_id, original, sha),
            "raw_size_bytes": len(original.raw_bytes),
            "raw_sha256": sha,
        }
    return fields


def _upload(fields: dict[str, Any], original: SourceOriginal) -> None:
    if fields["raw_storage_path"]:
        supabase.storage.from_(BUCKET).upload(
            fields["raw_storage_path"], original.raw_bytes,
            {"content-type": original.raw_mime or "application/octet-stream"},
        )


def _remove_objects(paths: list[str]) -> None:
    for batch in id_batches([p for p in paths if p], 100):
        supabase.storage.from_(BUCKET).remove(batch)


class ReplaceInProgress(RuntimeError):
    """Another replace of this source is running."""


@dataclass
class SourceWrite:
    """An ingest in progress. The caller writes its chunks with `ingest_id`, then
    calls commit(), or abort() if the chunk write failed."""
    user_id: str
    source_id: str
    ingest_id: str
    fields: dict[str, Any]
    pending: dict | None = None   # a replace's `pending_replace`; None for a new source

    def commit(self) -> None:
        if self.pending is None:
            mark_ready(self.source_id, self.user_id)
            return
        # The row switches to the new content and chunk set; pending_replace stays
        # set until the old set is gone, so a crash in between is finished, not undone.
        supabase.table("sources").update(
            {**self.fields, "status": "ready", "ingest_id": self.ingest_id, "updated_at": _now()}
        ).eq("source_id", self.source_id).eq("user_id", self.user_id).execute()
        _finish_replace(self.user_id, self.source_id, self.pending)

    def abort(self) -> None:
        if self.pending is None:
            discard_source(self.source_id, self.user_id)
        else:
            _undo_replace(self.user_id, self.source_id, self.pending)


def begin_source(user_id: str, source_id: str, original: SourceOriginal, *,
                 title: str, extracted_text: str, content_hash: str) -> SourceWrite:
    """Steps 1-2 for a new source. On an upload failure the row is removed and the error raised."""
    fields = _content_fields(user_id, source_id, original, title=title,
                             extracted_text=extracted_text, content_hash=content_hash)
    write = SourceWrite(user_id, source_id, new_ingest_id(), fields)
    supabase.table("sources").insert(
        {"source_id": source_id, "user_id": user_id, "ingest_id": write.ingest_id, **fields}
    ).execute()
    try:
        _upload(fields, original)
    except Exception:
        discard_source(source_id, user_id)
        raise
    return write


def begin_replace(user_id: str, source_id: str, original: SourceOriginal, *,
                  title: str, extracted_text: str, content_hash: str) -> SourceWrite:
    """New content for an existing source (same source_id). The old content,
    chunks and object stay live until commit(); abort() or a crash leaves them
    intact. The row records the replace in `pending_replace` first, so a crash
    can be cleaned up. One replace per source at a time: a running one raises
    ReplaceInProgress, a stale one (crashed) is cleaned up first."""
    old = get_source(source_id, user_id)
    if old is None:
        raise LookupError(f"source {source_id} not found")
    if old.get("pending_replace") and datetime.fromisoformat(old["updated_at"]) < _stale_cutoff_dt():
        _resolve_stale_replace(old)
    fields = _content_fields(user_id, source_id, original, title=title,
                             extracted_text=extracted_text, content_hash=content_hash)
    fields.pop("status")
    pending = {"ingest_id": new_ingest_id(), "raw_storage_path": fields["raw_storage_path"],
               "old_storage_path": old.get("raw_storage_path")}
    claimed = (supabase.table("sources").update({"pending_replace": pending, "updated_at": _now()})
               .eq("source_id", source_id).eq("user_id", user_id).is_("pending_replace", "null")
               .execute().data)
    if not claimed:
        raise ReplaceInProgress(f"source {source_id} is being replaced")
    try:
        if pending["raw_storage_path"] != pending["old_storage_path"]:
            _upload(fields, original)
    except Exception:
        _undo_replace(user_id, source_id, pending)
        raise
    return SourceWrite(user_id, source_id, pending["ingest_id"], fields, pending)


def _undo_replace(user_id: str, source_id: str, pending: dict) -> None:
    """Remove a replace's new chunk set and object; the old content stays."""
    derived_store.delete_chunks(
        derived_store.chunk_ids_of_sources([source_id], user_id, only_ingest=pending["ingest_id"]), user_id)
    if pending.get("raw_storage_path") and pending["raw_storage_path"] != pending.get("old_storage_path"):
        _remove_objects([pending["raw_storage_path"]])
    _clear_pending(user_id, source_id)


def _finish_replace(user_id: str, source_id: str, pending: dict) -> None:
    """After the row switched to the new set: delete every other chunk set (with
    its derived data) and the old object."""
    derived_store.delete_chunks(
        derived_store.chunk_ids_of_sources([source_id], user_id, except_ingest=pending["ingest_id"]), user_id)
    if pending.get("old_storage_path") and pending["old_storage_path"] != pending.get("raw_storage_path"):
        _remove_objects([pending["old_storage_path"]])
    _clear_pending(user_id, source_id)


def _clear_pending(user_id: str, source_id: str) -> None:
    supabase.table("sources").update({"pending_replace": None}) \
        .eq("source_id", source_id).eq("user_id", user_id).execute()


def _resolve_stale_replace(row: dict) -> None:
    """A replace that crashed: finished if the row had switched to its set, else undone."""
    pending = row["pending_replace"]
    if row.get("ingest_id") == pending["ingest_id"]:
        _finish_replace(row["user_id"], row["source_id"], pending)
    else:
        _undo_replace(row["user_id"], row["source_id"], pending)


def _stale_cutoff_dt(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) - STALE_PENDING_AFTER


def _stale_cutoff(now: datetime | None = None) -> str:
    return _stale_cutoff_dt(now).isoformat()


def mark_ready(source_id: str, user_id: str) -> None:
    supabase.table("sources").update({"status": "ready", "updated_at": _now()}) \
        .eq("source_id", source_id).eq("user_id", user_id).execute()


def get_source(source_id: str, user_id: str) -> dict | None:
    rows = (supabase.table("sources").select("*").eq("source_id", source_id)
            .eq("user_id", user_id).limit(1).execute().data or [])
    return rows[0] if rows else None


def find_source_id(user_id: str, input_type: str) -> str | None:
    """The user's newest source of this input type (for one-per-user sources
    like the business profile note)."""
    rows = (supabase.table("sources").select("source_id").eq("user_id", user_id)
            .eq("input_type", input_type).order("created_at", desc=True).limit(1).execute().data or [])
    return rows[0]["source_id"] if rows else None


def discard_source(source_id: str, user_id: str) -> None:
    """Remove a source completely: its Storage object, its chunks and its row."""
    delete_sources([source_id], user_id)


def delete_sources(source_ids: list[str], user_id: str) -> int:
    """Remove these sources: their objects (and a running replace's), chunks,
    rows, and everything derived from them (memory/derived_store.py). Returns
    rows removed."""
    if not source_ids:
        return 0
    rows = (supabase.table("sources").select("source_id,raw_storage_path,pending_replace")
            .in_("source_id", source_ids).eq("user_id", user_id).execute().data or [])
    derived_store.delete_chunks(derived_store.chunk_ids_of_sources(source_ids, user_id), user_id)
    _remove_objects([r.get("raw_storage_path") for r in rows]
                    + [(r.get("pending_replace") or {}).get("raw_storage_path") for r in rows])
    supabase.table("sources").delete().in_("source_id", source_ids).eq("user_id", user_id).execute()
    derived_store.after_sources_deleted({r["source_id"] for r in rows}, user_id)
    return len(rows)


def delete_source(source_id: str, user_id: str) -> int | None:
    """Library delete: one source, by id (titles are not unique). Returns the
    chunks removed, or None when the user has no source with this id."""
    if get_source(source_id, user_id) is None:
        return None
    chunks = len(derived_store.chunk_ids_of_sources([source_id], user_id))
    delete_sources([source_id], user_id)
    return chunks


def delete_all_for_user(user_id: str) -> int:
    """Account deletion: every source of the user, with its object and chunks."""
    ids = [r["source_id"] for r in (supabase.table("sources").select("source_id")
                                    .eq("user_id", user_id).execute().data or [])]
    return sum(delete_sources(batch, user_id) for batch in id_batches(ids))


def sweep_stale_pending(now: datetime | None = None) -> int:
    """Maintenance across all users: remove sources left 'pending', and the new
    chunk sets of replaces left running, longer than STALE_PENDING_AFTER (an
    ingest that crashed mid-write). Each removal is scoped to the row's own user_id."""
    cutoff = _stale_cutoff(now)
    rows = (supabase.table("sources").select("source_id,user_id").eq("status", "pending")
            .lt("updated_at", cutoff).execute().data or [])
    for row in rows:
        try:
            discard_source(row["source_id"], row["user_id"])
            logger.warning("removed stale pending source %s", row["source_id"])
        except Exception:
            logger.exception("could not remove stale pending source %s", row["source_id"])
    replaces = (supabase.table("sources").select("source_id,user_id,ingest_id,pending_replace")
                .not_.is_("pending_replace", "null").lt("updated_at", cutoff).execute().data or [])
    for row in replaces:
        try:
            _resolve_stale_replace(row)
            logger.warning("removed stale replace of source %s", row["source_id"])
        except Exception:
            logger.exception("could not remove stale replace of source %s", row["source_id"])
    return len(rows) + len(replaces)


async def _sweep_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(sweep_stale_pending)
        except Exception:
            logger.exception("stale pending source sweep failed")
        await asyncio.sleep(SWEEP_EVERY_SECONDS)


def start_sweeper() -> asyncio.Task:
    """Sweep at startup (after a crash) and then hourly."""
    return asyncio.create_task(_sweep_forever(), name="source-sweeper")
