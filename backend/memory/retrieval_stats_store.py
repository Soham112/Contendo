"""retrieval_stats_store.py — Tracks how often each source is retrieved during generation.

Table: source_retrieval_stats (Supabase Postgres), unique on (user_id, source_title)

Exposed API:
    init_retrieval_stats_db()                               — no-op (table exists in Supabase)
    record_retrievals(user_id, source_titles)               — count += 1 per distinct title, one read + one upsert
    record_retrievals_in_background(user_id, source_titles) — same, queued off the request path
    flush_pending_retrievals()                              — wait for queued writes (shutdown, tests)
    get_retrieval_counts(user_id) -> dict                   — {source_title: count} for all sources
"""

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

# One worker: queued writes run in order, so two generations by the same user in
# this process never read the same count and lose an increment. The backend runs
# one uvicorn worker; across processes the read-then-upsert could still race.
_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="retrieval-stats")


def init_retrieval_stats_db() -> None:
    """No-op — source_retrieval_stats table already exists in Supabase."""
    pass


def record_retrievals(user_id: str, source_titles: list[str]) -> None:
    """Increment retrieval_count by 1 for each distinct, non-empty title."""
    titles = list(dict.fromkeys(t.strip() for t in source_titles if t and t.strip()))
    if not titles:
        return
    now = datetime.now(timezone.utc).isoformat()
    existing = (
        supabase.table("source_retrieval_stats")
        .select("source_title,retrieval_count")
        .eq("user_id", user_id)
        .in_("source_title", titles)
        .execute()
    )
    counts = {row["source_title"]: row["retrieval_count"] or 0 for row in (existing.data or [])}
    supabase.table("source_retrieval_stats").upsert(
        [
            {
                "user_id": user_id,
                "source_title": title,
                "retrieval_count": counts.get(title, 0) + 1,
                "last_retrieved_at": now,
            }
            for title in titles
        ],
        on_conflict="user_id,source_title",
    ).execute()


def _record_quietly(user_id: str, source_titles: list[str]) -> None:
    try:
        record_retrievals(user_id, source_titles)
    except Exception as exc:
        logger.warning("retrieval stats write failed (non-critical): %s", exc)


def record_retrievals_in_background(user_id: str, source_titles: list[str]) -> Future:
    """Queue record_retrievals; returns at once. Failures are logged, never raised."""
    return _writer.submit(_record_quietly, user_id, list(source_titles))


def flush_pending_retrievals() -> None:
    """Block until every queued stats write has run."""
    _writer.submit(lambda: None).result()


def get_retrieval_counts(user_id: str) -> dict[str, int]:
    """Return a mapping of source_title -> retrieval_count for the given user."""
    result = (
        supabase.table("source_retrieval_stats")
        .select("source_title,retrieval_count")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["source_title"]: row["retrieval_count"] for row in (result.data or [])}
