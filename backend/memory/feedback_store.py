import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "data" / "posts.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            topic             TEXT NOT NULL,
            format            TEXT NOT NULL,
            tone              TEXT NOT NULL,
            content           TEXT NOT NULL,
            authenticity_score INTEGER NOT NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN svg_diagrams TEXT")
    except Exception:
        pass  # column already exists
    conn.commit()
    conn.close()


def log_post(
    topic: str,
    format: str,
    tone: str,
    content: str,
    authenticity_score: int,
    svg_diagrams: str | None = None,
) -> int:
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO posts (topic, format, tone, content, authenticity_score, svg_diagrams)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (topic, format, tone, content, authenticity_score, svg_diagrams),
    )
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id


def get_recent_posts(limit: int = 20) -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_topics_posted() -> list[str]:
    conn = _connect()
    rows = conn.execute("SELECT topic FROM posts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row["topic"] for row in rows]


_UNSET = object()


def update_post(
    post_id: int,
    content=_UNSET,
    authenticity_score=_UNSET,
    svg_diagrams=_UNSET,
) -> bool:
    """Update only the fields that are explicitly provided. _UNSET means skip that field."""
    fields = []
    values = []
    if content is not _UNSET:
        fields.append("content = ?")
        values.append(content)
    if authenticity_score is not _UNSET:
        fields.append("authenticity_score = ?")
        values.append(authenticity_score)
    if svg_diagrams is not _UNSET:
        fields.append("svg_diagrams = ?")
        values.append(svg_diagrams)
    if not fields:
        return False
    values.append(post_id)
    conn = _connect()
    cursor = conn.execute(
        f"UPDATE posts SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_post(post_id: int) -> bool:
    conn = _connect()
    cursor = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
