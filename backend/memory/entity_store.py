import logging
from typing import Any

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def upsert_entity(user_id: str, entity_name: str, entity_type: str) -> str:
    """Insert entity if it doesn't exist; return its entity_id either way.

    Uses the UNIQUE (user_id, entity_name, entity_type) constraint to
    deduplicate. Does a select-first to avoid unnecessary writes on the
    hot path (same entity mentioned across many chunks).
    """
    # Fast path: entity already exists
    result = (
        supabase.table("entities")
        .select("entity_id")
        .eq("user_id", user_id)
        .eq("entity_name", entity_name)
        .eq("entity_type", entity_type)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["entity_id"]

    # Slow path: insert new entity
    inserted = (
        supabase.table("entities")
        .insert({
            "user_id": user_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
        })
        .execute()
    )
    entity_id: str = inserted.data[0]["entity_id"]
    logger.debug("entity created: %s (%s) for user %s", entity_name, entity_type, user_id)
    return entity_id


def upsert_chunk_entities(
    chunk_id: str,
    user_id: str,
    entities: list[dict[str, str]],
) -> None:
    """Store entity–chunk junction rows for a single chunk.

    entities: list of dicts with keys entity_id, relationship_type.
    Rows with the same (chunk_id, entity_id) primary key are upserted
    idempotently so re-ingesting the same source is safe.
    """
    if not entities:
        return
    rows = [
        {
            "chunk_id": chunk_id,
            "entity_id": e["entity_id"],
            "user_id": user_id,
            "relationship_type": e["relationship_type"],
        }
        for e in entities
    ]
    supabase.table("chunk_entities").upsert(
        rows, on_conflict="chunk_id,entity_id"
    ).execute()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_entities_for_user(user_id: str) -> list[dict[str, Any]]:
    """Return all entities for a user."""
    result = (
        supabase.table("entities")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def get_entity_names_for_user(user_id: str) -> dict[str, str]:
    """Return {entity_name: node_type} map for fast cross-reference lookups.

    node_type here is actually entity_type — used by the memory context
    cross-reference logic to match against experience_nodes entity names.
    Only returns entities of type "company", "project", and "technology"
    since those are the types that map to work/personal_project experience.
    """
    result = (
        supabase.table("entities")
        .select("entity_name, entity_type")
        .eq("user_id", user_id)
        .in_("entity_type", ["company", "project", "technology"])
        .execute()
    )
    return {
        row["entity_name"].lower(): row["entity_type"]
        for row in (result.data or [])
    }


def get_entities_for_chunk(chunk_id: str, user_id: str) -> list[dict[str, Any]]:
    """Return all entities linked to a specific chunk."""
    result = (
        supabase.table("chunk_entities")
        .select("entity_id, relationship_type, entities(entity_name, entity_type)")
        .eq("chunk_id", chunk_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = []
    for row in (result.data or []):
        entity = row.get("entities") or {}
        rows.append({
            "entity_id": row["entity_id"],
            "entity_name": entity.get("entity_name", ""),
            "entity_type": entity.get("entity_type", ""),
            "relationship_type": row["relationship_type"],
        })
    return rows


def get_chunk_ids_for_entity(entity_id: str, user_id: str) -> list[str]:
    """Return all chunk_ids linked to an entity. Used in Phase 4 retrieval."""
    result = (
        supabase.table("chunk_entities")
        .select("chunk_id")
        .eq("entity_id", entity_id)
        .eq("user_id", user_id)
        .execute()
    )
    return [row["chunk_id"] for row in (result.data or [])]
