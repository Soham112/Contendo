import uuid
from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase


# ---------------------------------------------------------------------------
# No-op init — tables already exist in Supabase
# ---------------------------------------------------------------------------

def init_db() -> None:
    pass


# ---------------------------------------------------------------------------
# Source nodes
# ---------------------------------------------------------------------------

def upsert_source_node(
    source_id: str,
    user_id: str,
    source_title: str,
    source_type: str,
    ingested_at: str,
    tags: list[str],
    total_chunks: int,
    topic_id: str,
    source_summary: str,
) -> None:
    supabase.table("source_nodes").upsert({
        "source_id": source_id,
        "user_id": user_id,
        "source_title": source_title,
        "source_type": source_type,
        "ingested_at": ingested_at,
        "tags": ",".join(tags),
        "total_chunks": total_chunks,
        "topic_id": topic_id,
        "source_summary": source_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id,source_id").execute()


def get_source_node(source_id: str, user_id: str) -> dict[str, Any] | None:
    result = (
        supabase.table("source_nodes")
        .select("*")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    return _parse_source_row(result.data[0])


def get_source_nodes(source_ids: list[str], user_id: str) -> dict[str, dict[str, Any]]:
    """Source nodes for many source_ids in one query, keyed by source_id.

    Ids with no node (pre-migration sources) are absent from the result.
    """
    if not source_ids:
        return {}
    result = (
        supabase.table("source_nodes")
        .select("*")
        .in_("source_id", list(source_ids))
        .eq("user_id", user_id)
        .execute()
    )
    return {row["source_id"]: _parse_source_row(row) for row in (result.data or [])}


def _parse_source_row(row: dict[str, Any]) -> dict[str, Any]:
    row["tags"] = [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
    return row


def source_node_exists(source_id: str, user_id: str) -> bool:
    result = (
        supabase.table("source_nodes")
        .select("source_id")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def get_sources_for_user(user_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("source_nodes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_parse_source_row(row) for row in (result.data or [])]


# ---------------------------------------------------------------------------
# Topic nodes
# ---------------------------------------------------------------------------

def upsert_topic_node(
    topic_id: str,
    user_id: str,
    topic_label: str,
    topic_summary: str,
    representative_tags: list[str],
    child_source_ids: list[str],
) -> None:
    supabase.table("topic_nodes").upsert({
        "topic_id": topic_id,
        "user_id": user_id,
        "topic_label": topic_label,
        "topic_summary": topic_summary,
        "representative_tags": ",".join(representative_tags),
        "child_source_ids": ",".join(child_source_ids),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id,topic_id").execute()


def get_topic_node(topic_id: str, user_id: str) -> dict[str, Any] | None:
    result = (
        supabase.table("topic_nodes")
        .select("*")
        .eq("topic_id", topic_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    return _parse_topic_row(result.data[0])


def get_topic_nodes(topic_ids: list[str], user_id: str) -> dict[str, dict[str, Any]]:
    """Topic nodes for many topic_ids in one query, keyed by topic_id."""
    if not topic_ids:
        return {}
    result = (
        supabase.table("topic_nodes")
        .select("*")
        .in_("topic_id", list(topic_ids))
        .eq("user_id", user_id)
        .execute()
    )
    return {row["topic_id"]: _parse_topic_row(row) for row in (result.data or [])}


def _parse_topic_row(row: dict[str, Any]) -> dict[str, Any]:
    row["representative_tags"] = [
        t.strip() for t in (row.get("representative_tags") or "").split(",") if t.strip()
    ]
    row["child_source_ids"] = [
        s.strip() for s in (row.get("child_source_ids") or "").split(",") if s.strip()
    ]
    return row


def get_topics_for_user(user_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("topic_nodes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_parse_topic_row(row) for row in (result.data or [])]


def find_matching_topic(tags: list[str], user_id: str) -> dict[str, Any] | None:
    """Return the first topic node that shares 2+ tags with the given tag list.

    Pure Python scan — topic counts are small (< 50 typically).
    Returns None if no match found.
    """
    if not tags:
        return None
    tag_set = set(t.lower().strip() for t in tags if t.strip())
    topics = get_topics_for_user(user_id)
    for topic in topics:
        topic_tags = set(t.lower().strip() for t in topic.get("representative_tags", []))
        if len(tag_set & topic_tags) >= 2:
            return topic
    return None


def add_source_to_topic(topic_id: str, source_id: str, user_id: str) -> None:
    """Idempotently append source_id to a topic's child_source_ids."""
    topic = get_topic_node(topic_id, user_id)
    if not topic:
        return
    existing = topic.get("child_source_ids", [])
    if source_id in existing:
        return
    updated = existing + [source_id]
    supabase.table("topic_nodes").update({
        "child_source_ids": ",".join(updated),
    }).eq("topic_id", topic_id).eq("user_id", user_id).execute()


def remove_sources_from_topics(source_ids: set[str], user_id: str) -> None:
    """Drop deleted sources from their topics' children. A topic left empty stays:
    find_matching_topic can give it to the next source with the same tags."""
    for topic in get_topics_for_user(user_id):
        kids = topic.get("child_source_ids", [])
        kept = [k for k in kids if k not in source_ids]
        if kept != kids:
            supabase.table("topic_nodes").update({"child_source_ids": ",".join(kept)}) \
                .eq("topic_id", topic["topic_id"]).eq("user_id", user_id).execute()


def assign_source_to_topic(source_id: str, tags: list[str], user_id: str) -> str:
    """Assign source to an existing topic (2+ tag overlap) or create a new one.

    Returns the topic_id assigned.
    """
    existing_topic = find_matching_topic(tags, user_id=user_id)
    if existing_topic:
        topic_id = existing_topic["topic_id"]
        add_source_to_topic(topic_id, source_id, user_id=user_id)
        return topic_id

    # No matching topic — create one with the first tag as the label
    topic_id = str(uuid.uuid4())
    topic_label = tags[0] if tags else "general"
    upsert_topic_node(
        topic_id=topic_id,
        user_id=user_id,
        topic_label=topic_label,
        topic_summary="",
        representative_tags=tags,
        child_source_ids=[source_id],
    )
    return topic_id

