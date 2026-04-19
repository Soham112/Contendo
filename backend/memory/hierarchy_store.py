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
    }, on_conflict="source_id").execute()


def get_source_node(source_id: str, user_id: str = "default") -> dict[str, Any] | None:
    result = (
        supabase.table("source_nodes")
        .select("*")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    row["tags"] = [t.strip() for t in row.get("tags", "").split(",") if t.strip()]
    return row


def source_node_exists(source_id: str, user_id: str = "default") -> bool:
    result = (
        supabase.table("source_nodes")
        .select("source_id")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def get_sources_for_user(user_id: str = "default") -> list[dict[str, Any]]:
    result = (
        supabase.table("source_nodes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    results = []
    for row in (result.data or []):
        row["tags"] = [t.strip() for t in row.get("tags", "").split(",") if t.strip()]
        results.append(row)
    return results


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
    }, on_conflict="topic_id").execute()


def get_topic_node(topic_id: str, user_id: str = "default") -> dict[str, Any] | None:
    result = (
        supabase.table("topic_nodes")
        .select("*")
        .eq("topic_id", topic_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    row["representative_tags"] = [
        t.strip() for t in row.get("representative_tags", "").split(",") if t.strip()
    ]
    row["child_source_ids"] = [
        s.strip() for s in row.get("child_source_ids", "").split(",") if s.strip()
    ]
    return row


def get_topics_for_user(user_id: str = "default") -> list[dict[str, Any]]:
    result = (
        supabase.table("topic_nodes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    results = []
    for row in (result.data or []):
        row["representative_tags"] = [
            t.strip() for t in row.get("representative_tags", "").split(",") if t.strip()
        ]
        row["child_source_ids"] = [
            s.strip() for s in row.get("child_source_ids", "").split(",") if s.strip()
        ]
        results.append(row)
    return results


def find_matching_topic(tags: list[str], user_id: str = "default") -> dict[str, Any] | None:
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


def add_source_to_topic(topic_id: str, source_id: str, user_id: str = "default") -> None:
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
