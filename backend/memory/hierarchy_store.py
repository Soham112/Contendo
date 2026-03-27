import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "data" / "hierarchy.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_nodes (
            source_id       TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL DEFAULT 'default',
            source_title    TEXT,
            source_type     TEXT,
            ingested_at     TEXT,
            tags            TEXT,
            total_chunks    INTEGER,
            topic_id        TEXT,
            source_summary  TEXT,
            created_at      TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topic_nodes (
            topic_id            TEXT PRIMARY KEY,
            user_id             TEXT NOT NULL DEFAULT 'default',
            topic_label         TEXT,
            topic_summary       TEXT,
            representative_tags TEXT,
            child_source_ids    TEXT,
            created_at          TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_nodes_user_id ON source_nodes(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_topic_nodes_user_id ON topic_nodes(user_id)"
    )
    conn.commit()
    conn.close()


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
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO source_nodes
            (source_id, user_id, source_title, source_type, ingested_at,
             tags, total_chunks, topic_id, source_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            user_id,
            source_title,
            source_type,
            ingested_at,
            ",".join(tags),
            total_chunks,
            topic_id,
            source_summary,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_source_node(source_id: str, user_id: str = "default") -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM source_nodes WHERE source_id = ? AND user_id = ?",
        (source_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["tags"] = [t.strip() for t in result.get("tags", "").split(",") if t.strip()]
    return result


def source_node_exists(source_id: str, user_id: str = "default") -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM source_nodes WHERE source_id = ? AND user_id = ? LIMIT 1",
        (source_id, user_id),
    ).fetchone()
    conn.close()
    return row is not None


def get_sources_for_user(user_id: str = "default") -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM source_nodes WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        r["tags"] = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
        results.append(r)
    return results


def upsert_topic_node(
    topic_id: str,
    user_id: str,
    topic_label: str,
    topic_summary: str,
    representative_tags: list[str],
    child_source_ids: list[str],
) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO topic_nodes
            (topic_id, user_id, topic_label, topic_summary,
             representative_tags, child_source_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            topic_id,
            user_id,
            topic_label,
            topic_summary,
            ",".join(representative_tags),
            ",".join(child_source_ids),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_topic_node(topic_id: str, user_id: str = "default") -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM topic_nodes WHERE topic_id = ? AND user_id = ?",
        (topic_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["representative_tags"] = [
        t.strip() for t in result.get("representative_tags", "").split(",") if t.strip()
    ]
    result["child_source_ids"] = [
        s.strip() for s in result.get("child_source_ids", "").split(",") if s.strip()
    ]
    return result


def get_topics_for_user(user_id: str = "default") -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM topic_nodes WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        r["representative_tags"] = [
            t.strip() for t in r.get("representative_tags", "").split(",") if t.strip()
        ]
        r["child_source_ids"] = [
            s.strip() for s in r.get("child_source_ids", "").split(",") if s.strip()
        ]
        results.append(r)
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
    conn = _connect()
    conn.execute(
        "UPDATE topic_nodes SET child_source_ids = ? WHERE topic_id = ? AND user_id = ?",
        (",".join(updated), topic_id, user_id),
    )
    conn.commit()
    conn.close()
