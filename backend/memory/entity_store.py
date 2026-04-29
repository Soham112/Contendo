import logging
import re
from typing import Any

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity name normalization
# ---------------------------------------------------------------------------

# Suffixes that are meaningless for deduplication — stripped before lookup.
# Ordered longest-first so ".js" doesn't shadow "node.js".
_STRIP_SUFFIXES = [
    "framework", "platform", "library", "language", "database", "db",
    ".js", ".ts", ".py", ".io",
]

def _normalize_entity_name(name: str) -> str:
    """Return a canonical form of an entity name for deduplication.

    Steps (order matters):
    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace.
    3. Remove common noise punctuation (hyphens, dots outside version numbers,
       parentheses) that create false variants ("React.js" → "react js" → "react").
    4. Strip known meaningless suffixes ("framework", ".js", ".py", etc.).
    5. Lowercase and strip again.

    Examples:
      "React.js"      → "react"
      "ReactJS"       → "reactjs"   (camelCase is kept — too risky to split)
      "Open AI"       → "open ai"
      "OpenAI"        → "openai"
      "Node.js"       → "nodejs"    (.js stripped after dot removal)
      "PostgreSQL"    → "postgresql"
      "Postgres"      → "postgres"  (these stay distinct — different spellings)
      "LangChain"     → "langchain"
      "LangChain (framework)" → "langchain"
    """
    s = name.strip()

    # Remove parenthetical qualifiers e.g. "Python (language)"
    s = re.sub(r"\s*\(.*?\)", "", s)

    # Remove hyphens and dots that aren't between digits (preserve "3.11", "gpt-4")
    s = re.sub(r"(?<!\d)[.\-](?!\d)", " ", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # Strip known meaningless suffixes (word-boundary aware)
    lower = s.lower()
    for suffix in _STRIP_SUFFIXES:
        if lower.endswith(" " + suffix):
            s = s[: -(len(suffix) + 1)].strip()
            lower = s.lower()
            break
        if lower.endswith(suffix) and len(s) > len(suffix) + 2:
            s = s[: -len(suffix)].strip()
            lower = s.lower()
            break

    return s.lower().strip()


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def upsert_entity(user_id: str, entity_name: str, entity_type: str) -> str:
    """Insert entity if it doesn't exist; return its entity_id either way.

    Normalizes entity_name before lookup so surface-form variants
    ("React.js", "ReactJS", "react") collapse to the same canonical row.
    The canonical (normalized) name is what gets stored — raw extraction
    output is never written directly.

    Uses the UNIQUE (user_id, entity_name, entity_type) constraint for
    final-level deduplication. Does a select-first to avoid unnecessary
    writes on the hot path (same entity mentioned across many chunks).
    """
    canonical = _normalize_entity_name(entity_name)
    if not canonical:
        canonical = entity_name.lower().strip()

    # Fast path: entity already exists under canonical name
    result = (
        supabase.table("entities")
        .select("entity_id")
        .eq("user_id", user_id)
        .eq("entity_name", canonical)
        .eq("entity_type", entity_type)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["entity_id"]

    # Slow path: insert new entity with canonical name
    inserted = (
        supabase.table("entities")
        .insert({
            "user_id": user_id,
            "entity_name": canonical,
            "entity_type": entity_type,
        })
        .execute()
    )
    entity_id: str = inserted.data[0]["entity_id"]
    logger.debug(
        "entity created: %r → canonical %r (%s) for user %s",
        entity_name, canonical, entity_type, user_id,
    )
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


def get_entities_with_source_count(
    user_id: str, min_sources: int = 3
) -> list[dict[str, Any]]:
    """Return entities that appear in at least min_sources distinct sources.

    chunk_id format is '{source_id}_{chunk_index}' — source_id is extracted
    by rsplit('_', 1)[0] since source_ids are UUIDs with no trailing underscore.

    Returns list of dicts: {entity_id, entity_name, entity_type, source_count}.
    Used by the consolidation agent to find entities ready for synthesis.
    """
    # Fetch all chunk_entities for the user in one query
    result = (
        supabase.table("chunk_entities")
        .select("entity_id, chunk_id")
        .eq("user_id", user_id)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return []

    # Count distinct source_ids per entity_id (source_id = chunk_id without last _N)
    entity_sources: dict[str, set[str]] = {}
    for row in rows:
        entity_id = row["entity_id"]
        chunk_id = row["chunk_id"]
        source_id = chunk_id.rsplit("_", 1)[0]
        entity_sources.setdefault(entity_id, set()).add(source_id)

    qualifying_ids = [
        eid for eid, sources in entity_sources.items()
        if len(sources) >= min_sources
    ]
    if not qualifying_ids:
        return []

    # Fetch entity metadata for qualifying ids
    entity_result = (
        supabase.table("entities")
        .select("entity_id, entity_name, entity_type")
        .eq("user_id", user_id)
        .in_("entity_id", qualifying_ids)
        .execute()
    )
    return [
        {
            **row,
            "source_count": len(entity_sources[row["entity_id"]]),
        }
        for row in (entity_result.data or [])
    ]
