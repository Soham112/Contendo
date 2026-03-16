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
    conn.commit()
    conn.close()


def log_post(
    topic: str,
    format: str,
    tone: str,
    content: str,
    authenticity_score: int,
) -> int:
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO posts (topic, format, tone, content, authenticity_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (topic, format, tone, content, authenticity_score),
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
