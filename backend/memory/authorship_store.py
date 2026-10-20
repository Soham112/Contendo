"""Writes a stored source's authorship after ingest (step 3.3): the user's
choice (PATCH /sources/{id}/authorship) and the backfill's classifier result,
each rewriting embeddings.chunk_authorship for the source's live chunk set.

At ingest the labels are written with the source row and its chunks
(agents/ingestion_agent.py); this module is for sources already stored.
Chunk labels come from the spans in authorship_detail (offsets into
extracted_text) through utils.provenance_spans.chunk_labels.
"""
from __future__ import annotations

import logging

from db import id_batches
from db.supabase_client import supabase
from memory.source_store import ReplaceInProgress, _now, get_source
from utils.chunker import chunk_spans
from utils.provenance_spans import chunk_labels

logger = logging.getLogger(__name__)

# What the user may choose; user_stated and system_inferred are set by rule only.
USER_CHOICES = frozenset({"user_authored", "external"})


def _live_chunks(row: dict, user_id: str) -> list[dict]:
    """The source's current chunk set, in order (chunks from before migration
    016 have no ingest_id; the row's ingest_id is then NULL too)."""
    rows = (supabase.table("embeddings").select("id,chunk_index,content,ingest_id")
            .eq("source_id", row["source_id"]).eq("user_id", user_id).eq("node_type", "chunk")
            .execute().data or [])
    live = [r for r in rows if r.get("ingest_id") == row.get("ingest_id")]
    return sorted(live, key=lambda r: r.get("chunk_index") or 0)


def relabel_chunks(row: dict, user_id: str, authorship: str | None, spans: list[dict]) -> bool:
    """Rewrite chunk_authorship of the source's live chunks for this source
    label and these spans. False when the stored chunks are not the chunking
    of extracted_text (a source rebuilt from chunks that did not rechunk
    exactly): the spans cannot be placed, so every chunk takes the source's
    label (NULL)."""
    chunks = _live_chunks(row, user_id)
    offsets = chunk_spans(row.get("extracted_text") or "")
    mapped = [c.text for c in offsets] == [c.get("content") for c in chunks]
    if mapped:
        labels = chunk_labels([(c.start, c.end) for c in offsets], authorship, spans)
    else:
        logger.warning("source %s: chunks are not the chunking of extracted_text; spans not mapped",
                       row["source_id"])
        labels = [None] * len(chunks)
    groups: dict[str | None, list[str]] = {}
    for chunk, label in zip(chunks, labels):
        groups.setdefault(label, []).append(chunk["id"])
    for label, ids in groups.items():
        for batch in id_batches(ids):
            (supabase.table("embeddings").update({"chunk_authorship": label})
             .in_("id", batch).eq("user_id", user_id).execute())
    return mapped


def _spans(row: dict) -> list[dict]:
    return list((row.get("authorship_detail") or {}).get("spans") or [])


def set_user_authorship(source_id: str, user_id: str, authorship: str) -> dict | None:
    """The user's choice for a source (it wins over rule and classifier, and is
    kept on Replace). None when the user has no such source. Raises
    ReplaceInProgress while a replace is running (its commit would overwrite
    the choice) and ValueError for a label the user may not set."""
    if authorship not in USER_CHOICES:
        raise ValueError(f"authorship must be one of {sorted(USER_CHOICES)}")
    row = get_source(source_id, user_id)
    if row is None:
        return None
    if row.get("pending_replace"):
        raise ReplaceInProgress(f"source {source_id} is being replaced")
    (supabase.table("sources")
     .update({"authorship": authorship, "authorship_set_by": "user", "updated_at": _now()})
     .eq("source_id", source_id).eq("user_id", user_id).execute())
    mapped = relabel_chunks(row, user_id, authorship, _spans(row))
    return {"source_id": source_id, "authorship": authorship, "authorship_set_by": "user",
            "spans_mapped": mapped}


def write_classifier_result(row: dict, user_id: str, *, authorship: str | None, detail: dict) -> bool:
    """A classifier result for a stored source (the backfill): detail always,
    authorship with set_by='classifier' only when given (confident). Only for a
    source nobody has labelled: skips one whose authorship was set meanwhile,
    or that is being replaced. Returns whether it wrote."""
    written = (supabase.table("sources")
               .update({"authorship": authorship,
                        "authorship_set_by": "classifier" if authorship else None,
                        "authorship_detail": detail, "updated_at": _now()})
               .eq("source_id", row["source_id"]).eq("user_id", user_id)
               .is_("authorship_set_by", "null").is_("pending_replace", "null")
               .execute().data)
    if not written:
        return False
    relabel_chunks(row, user_id, authorship, list(detail.get("spans") or []))
    return True
