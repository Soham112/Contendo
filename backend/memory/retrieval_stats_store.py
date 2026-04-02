"""retrieval_stats_store.py — Tracks how often each source is retrieved during generation.

Table: source_retrieval_stats
File: HIERARCHY_DB_PATH (same hierarchy.db — new table, not a new file)

Exposed API:
    init_retrieval_stats_db()                    — idempotent table + index creation
    increment_retrieval(user_id, source_title)   — upsert: count += 1, update timestamp
    get_retrieval_counts(user_id) -> dict         — {source_title: count} for all sources
"""

import sqlite3
import logging
from datetime import datetime, timezone

from config.paths import HIERARCHY_DB_PATH as DB_PATH

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_retrieval_stats_db() -> None:
    """Create source_retrieval_stats table in hierarchy.db if it doesn't exist."""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_retrieval_stats (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           TEXT NOT NULL,
            source_title      TEXT NOT NULL,
            retrieval_count   INTEGER NOT NULL DEFAULT 0,
            last_retrieved_at TIMESTAMP,
            UNIQUE (user_id, source_title)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_retrieval_stats_user_id "
        "ON source_retrieval_stats(user_id)"
    )
    conn.commit()
    conn.close()
    logger.info("[retrieval_stats_store] source_retrieval_stats table ready")


def increment_retrieval(user_id: str, source_title: str) -> None:
    """Increment retrieval_count for (user_id, source_title) by 1.

    Uses INSERT OR IGNORE + UPDATE to atomically create-or-increment without
    relying on non-portable ON CONFLICT DO UPDATE syntax.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        # Ensure row exists
        conn.execute(
            """
            INSERT OR IGNORE INTO source_retrieval_stats
                (user_id, source_title, retrieval_count, last_retrieved_at)
            VALUES (?, ?, 0, ?)
            """,
            (user_id, source_title, now),
        )
        # Increment
        conn.execute(
            """
            UPDATE source_retrieval_stats
               SET retrieval_count   = retrieval_count + 1,
                   last_retrieved_at = ?
             WHERE user_id = ? AND source_title = ?
            """,
            (now, user_id, source_title),
        )
        conn.commit()
    finally:
        conn.close()


def get_retrieval_counts(user_id: str) -> dict[str, int]:
    """Return a mapping of source_title -> retrieval_count for the given user."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT source_title, retrieval_count FROM source_retrieval_stats WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return {row["source_title"]: row["retrieval_count"] for row in rows}
