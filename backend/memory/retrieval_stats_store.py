"""retrieval_stats_store.py — Tracks how often each source is retrieved during generation.

Table: source_retrieval_stats (Supabase Postgres), unique on (user_id, source_id)
(migration 017). Keyed by source id because titles are not unique. The foreign
key to `sources` deletes a source's count with the source.

Exposed API:
    init_retrieval_stats_db()                               — no-op (table exists in Supabase)
    record_retrievals(user_id, source_ids)                  — count += 1 per distinct source of the user
    record_retrievals_in_background(user_id, source_ids)    — same, queued off the request path
    flush_pending_retrievals()                              — wait for queued writes (shutdown, tests)
    get_retrieval_counts(user_id) -> dict                   — {source_id: count}
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


def record_retrievals(user_id: str, source_ids: list[str]) -> None:
    """Increment retrieval_count by 1 for each distinct source id that is one of
    the user's sources. Other ids are skipped: a consolidation chunk's source_id
    is an entity id, and the foreign key would refuse the whole write."""
    wanted = list(dict.fromkeys(i for i in source_ids if i))
    if not wanted:
        return
    ids = [r["source_id"] for r in (supabase.table("sources").select("source_id").eq("user_id", user_id)
                                    .in_("source_id", wanted).execute().data or [])]
    if not ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    existing = (
        supabase.table("source_retrieval_stats")
        .select("source_id,retrieval_count")
        .eq("user_id", user_id)
        .in_("source_id", ids)
        .execute()
    )
    counts = {row["source_id"]: row["retrieval_count"] or 0 for row in (existing.data or [])}
    supabase.table("source_retrieval_stats").upsert(
        [
            {
                "user_id": user_id,
                "source_id": source_id,
                "retrieval_count": counts.get(source_id, 0) + 1,
                "last_retrieved_at": now,
            }
            for source_id in ids
        ],
        on_conflict="user_id,source_id",
    ).execute()


def _record_quietly(user_id: str, source_ids: list[str]) -> None:
    try:
        record_retrievals(user_id, source_ids)
    except Exception as exc:
        logger.warning("retrieval stats write failed (non-critical): %s", exc)


def record_retrievals_in_background(user_id: str, source_ids: list[str]) -> Future:
    """Queue record_retrievals; returns at once. Failures are logged, never raised."""
    return _writer.submit(_record_quietly, user_id, list(source_ids))


def flush_pending_retrievals() -> None:
    """Block until every queued stats write has run."""
    _writer.submit(lambda: None).result()


def get_retrieval_counts(user_id: str) -> dict[str, int]:
    """Return a mapping of source_id -> retrieval_count for the given user."""
    result = (
        supabase.table("source_retrieval_stats")
        .select("source_id,retrieval_count")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["source_id"]: row["retrieval_count"] for row in (result.data or []) if row.get("source_id")}
