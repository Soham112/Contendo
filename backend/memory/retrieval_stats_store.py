"""retrieval_stats_store.py — Tracks how often each source is retrieved during generation.

Table: source_retrieval_stats (Supabase Postgres)

Exposed API:
    init_retrieval_stats_db()                    — no-op (table exists in Supabase)
    increment_retrieval(user_id, source_title)   — upsert: count += 1, update timestamp
    get_retrieval_counts(user_id) -> dict         — {source_title: count} for all sources
"""

import logging
from datetime import datetime, timezone

from db.supabase_client import supabase

logger = logging.getLogger(__name__)


def init_retrieval_stats_db() -> None:
    """No-op — source_retrieval_stats table already exists in Supabase."""
    pass


def increment_retrieval(user_id: str, source_title: str) -> None:
    """Increment retrieval_count for (user_id, source_title) by 1."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = (
            supabase.table("source_retrieval_stats")
            .select("retrieval_count")
            .eq("user_id", user_id)
            .eq("source_title", source_title)
            .execute()
        )
        if existing.data:
            new_count = existing.data[0]["retrieval_count"] + 1
            supabase.table("source_retrieval_stats").update({
                "retrieval_count": new_count,
                "last_retrieved_at": now,
            }).eq("user_id", user_id).eq("source_title", source_title).execute()
        else:
            supabase.table("source_retrieval_stats").insert({
                "user_id": user_id,
                "source_title": source_title,
                "retrieval_count": 1,
                "last_retrieved_at": now,
            }).execute()
    except Exception:
        pass  # non-critical stat tracking


def get_retrieval_counts(user_id: str) -> dict[str, int]:
    """Return a mapping of source_title -> retrieval_count for the given user."""
    result = (
        supabase.table("source_retrieval_stats")
        .select("source_title,retrieval_count")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["source_title"]: row["retrieval_count"] for row in (result.data or [])}
