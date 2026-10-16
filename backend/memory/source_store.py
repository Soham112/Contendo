"""Originals of every ingested source: the `sources` table and the private
`source-originals` Storage bucket (migration 014).

Write order, so a crash can never leave an object or chunk nobody knows about:
  1. begin_source / begin_replace: the row, status 'pending' (names the object path)
  2. the Storage object, if the original is binary
  3. the chunks (by the caller, vector_store.upsert_chunks)
  4. mark_ready
A failure in 2-3 calls discard_source inline; a crash leaves a pending row that
sweep_stale_pending removes, with its object and chunks.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from db.supabase_client import supabase

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
    paths = [p for p in paths if p]
    for start in range(0, len(paths), 100):
        supabase.storage.from_(BUCKET).remove(paths[start:start + 100])


def begin_source(user_id: str, source_id: str, original: SourceOriginal, *,
                 title: str, extracted_text: str, content_hash: str) -> None:
    """Steps 1-2 for a new source. On an upload failure the row is removed and the error raised."""
    fields = _content_fields(user_id, source_id, original, title=title,
                             extracted_text=extracted_text, content_hash=content_hash)
    supabase.table("sources").insert({"source_id": source_id, "user_id": user_id, **fields}).execute()
    try:
        _upload(fields, original)
    except Exception:
        discard_source(source_id, user_id)
        raise


def begin_replace(user_id: str, source_id: str, original: SourceOriginal, *,
                  title: str, extracted_text: str, content_hash: str) -> None:
    """Steps 1-2 for new content of an existing source: the row is updated in
    place (same source_id) and its old chunks and old object are removed."""
    old = get_source(source_id, user_id)
    if old is None:
        raise LookupError(f"source {source_id} not found")
    fields = _content_fields(user_id, source_id, original, title=title,
                             extracted_text=extracted_text, content_hash=content_hash)
    supabase.table("sources").update(fields).eq("source_id", source_id).eq("user_id", user_id).execute()
    supabase.table("embeddings").delete().eq("source_id", source_id).eq("user_id", user_id).execute()
    try:
        _upload(fields, original)
    except Exception:
        discard_source(source_id, user_id)
        raise
    if old.get("raw_storage_path") and old["raw_storage_path"] != fields["raw_storage_path"]:
        _remove_objects([old["raw_storage_path"]])


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
    """Remove these sources' objects, chunks and rows. Returns rows removed."""
    if not source_ids:
        return 0
    rows = (supabase.table("sources").select("source_id,raw_storage_path")
            .in_("source_id", source_ids).eq("user_id", user_id).execute().data or [])
    _remove_objects([r.get("raw_storage_path") for r in rows])
    supabase.table("embeddings").delete().in_("source_id", source_ids).eq("user_id", user_id).execute()
    supabase.table("sources").delete().in_("source_id", source_ids).eq("user_id", user_id).execute()
    return len(rows)


def delete_all_for_user(user_id: str) -> int:
    """Account deletion: every source of the user, with its object and chunks."""
    ids = [r["source_id"] for r in (supabase.table("sources").select("source_id")
                                    .eq("user_id", user_id).execute().data or [])]
    removed = 0
    for start in range(0, len(ids), 200):
        removed += delete_sources(ids[start:start + 200], user_id)
    return removed


def sweep_stale_pending(now: datetime | None = None) -> int:
    """Maintenance across all users: remove sources left 'pending' longer than
    STALE_PENDING_AFTER (an ingest that crashed mid-write). Each removal is
    scoped to the row's own user_id."""
    cutoff = ((now or datetime.now(timezone.utc)) - STALE_PENDING_AFTER).isoformat()
    rows = (supabase.table("sources").select("source_id,user_id").eq("status", "pending")
            .lt("updated_at", cutoff).execute().data or [])
    for row in rows:
        try:
            discard_source(row["source_id"], row["user_id"])
            logger.warning("removed stale pending source %s", row["source_id"])
        except Exception:
            logger.exception("could not remove stale pending source %s", row["source_id"])
    return len(rows)


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
