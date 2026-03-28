import sqlite3
from pathlib import Path
from typing import Any

from config.paths import POSTS_DB_PATH as DB_PATH


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
            authenticity_score INTEGER NOT NULL,
            archetype         TEXT DEFAULT ''
        )
    """)
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN svg_diagrams TEXT")
    except Exception:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN archetype TEXT DEFAULT ''")
    except Exception:
        pass  # column already exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_versions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id           INTEGER NOT NULL,
            version_number    INTEGER NOT NULL,
            content           TEXT NOT NULL,
            authenticity_score INTEGER,
            version_type      TEXT NOT NULL,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            svg_diagrams      TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def log_post(
    topic: str,
    format: str,
    tone: str,
    content: str,
    authenticity_score: int,
    svg_diagrams: str | None = None,
    archetype: str = "",
) -> int:
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO posts (topic, format, tone, content, authenticity_score, svg_diagrams, archetype)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (topic, format, tone, content, authenticity_score, svg_diagrams, archetype),
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


def add_version(
    post_id: int,
    content: str,
    authenticity_score: int | None,
    version_type: str,
    svg_diagrams: str | None = None,
) -> int:
    """Insert a new version row for post_id. version_number is auto-incremented per post."""
    conn = _connect()
    row = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM post_versions WHERE post_id = ?",
        (post_id,),
    ).fetchone()
    next_version = row[0] + 1
    cursor = conn.execute(
        """
        INSERT INTO post_versions
            (post_id, version_number, content, authenticity_score, version_type, svg_diagrams)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (post_id, next_version, content, authenticity_score, version_type, svg_diagrams),
    )
    version_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return version_id


def get_versions(post_id: int) -> list[dict[str, Any]]:
    """Return all versions for a post ordered by version_number ascending."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM post_versions WHERE post_id = ? ORDER BY version_number ASC",
        (post_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_best_version(post_id: int) -> dict[str, Any] | None:
    """Return the version with the highest authenticity_score; latest version breaks ties."""
    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM post_versions
        WHERE post_id = ?
        ORDER BY authenticity_score DESC, version_number DESC
        LIMIT 1
        """,
        (post_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_latest_version_svg(post_id: int, svg_diagrams: str | None) -> bool:
    """Update svg_diagrams on the most recent version row without creating a new version."""
    conn = _connect()
    cursor = conn.execute(
        """
        UPDATE post_versions SET svg_diagrams = ?
        WHERE post_id = ? AND version_number = (
            SELECT MAX(version_number) FROM post_versions WHERE post_id = ?
        )
        """,
        (svg_diagrams, post_id, post_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
