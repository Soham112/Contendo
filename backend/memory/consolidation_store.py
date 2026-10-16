"""Consolidation store — manages memory consolidation chunks in the embeddings table.

Consolidation chunks are synthesised summaries of everything a user knows about
a specific entity, bucketed by memory context. They live in the existing
`embeddings` table with node_type="consolidation" so they are retrieved alongside
regular knowledge chunks with no schema changes.

Chunk ID format: "consolidation_{user_id}_{entity_id}"
One row per (user, entity) — upserted each time consolidation reruns.
"""
import logging
from typing import Any

from db import id_batches
from db.supabase_client import supabase
from memory.vector_store import embed_texts

logger = logging.getLogger(__name__)

CONSOLIDATION_NODE_TYPE = "consolidation"


def upsert_consolidation_chunk(
    user_id: str,
    entity_id: str,
    entity_name: str,
    content: str,
) -> None:
    """Embed and upsert a consolidation chunk for an entity.

    The chunk_id is deterministic so re-running consolidation on the same
    entity simply updates the existing row rather than creating duplicates.
    """
    chunk_id = f"consolidation_{user_id}_{entity_id}"
    embedding = embed_texts([content])[0]

    row: dict[str, Any] = {
        "id": chunk_id,
        "user_id": user_id,
        "content": content,
        "embedding": embedding,
        "source_id": entity_id,
        "source_title": f"[Consolidated knowledge: {entity_name}]",
        "source_type": "consolidation",
        "tags": entity_name.lower(),
        "chunk_index": 0,
        "total_chunks": 1,
        "content_hash": "",
        "node_type": CONSOLIDATION_NODE_TYPE,
        "memory_context": None,   # consolidation spans all contexts
        "ingested_at": None,
    }
    supabase.table("embeddings").upsert(row).execute()
    logger.info(
        "upsert_consolidation_chunk: entity=%r user=%s chunk_id=%s",
        entity_name, user_id, chunk_id,
    )


def get_consolidation_chunk(entity_id: str, user_id: str) -> dict[str, Any] | None:
    """Return the consolidation chunk for an entity, or None if not yet synthesised."""
    chunk_id = f"consolidation_{user_id}_{entity_id}"
    result = (
        supabase.table("embeddings")
        .select("id, content, source_title, ingested_at")
        .eq("id", chunk_id)
        .eq("user_id", user_id)
        .eq("node_type", CONSOLIDATION_NODE_TYPE)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_all_consolidation_chunks(user_id: str) -> list[dict[str, Any]]:
    """Return all consolidation chunks for a user."""
    result = (
        supabase.table("embeddings")
        .select("id, content, source_title, source_id, ingested_at")
        .eq("user_id", user_id)
        .eq("node_type", CONSOLIDATION_NODE_TYPE)
        .execute()
    )
    return result.data or []


def delete_consolidation_chunks(entity_ids: set[str], user_id: str) -> int:
    """Delete the consolidation chunks of these entities (one of their chunks was
    deleted, so a brief may hold text the user removed). Returns rows deleted."""
    removed = 0
    for batch in id_batches(sorted(entity_ids)):
        removed += len(
            supabase.table("embeddings").delete().in_("source_id", batch)
            .eq("user_id", user_id).eq("node_type", CONSOLIDATION_NODE_TYPE).execute().data or []
        )
    if removed:
        logger.info("delete_consolidation_chunks: %d removed for user %s", removed, user_id)
    return removed
