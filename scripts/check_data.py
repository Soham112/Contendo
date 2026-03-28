#!/usr/bin/env python3
"""Data verification utility for Contendo.

Run this before and after migrating data to Railway to confirm
that all expected files are present and contain real data.

Usage (local):
    cd backend
    python ../scripts/check_data.py

Usage (Railway shell / Docker exec):
    DATA_DIR=/data python /app/backend/../scripts/check_data.py
"""

import os
import sqlite3
import sys
from pathlib import Path

# Allow running from project root or backend/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from config.paths import CHROMA_DIR, HIERARCHY_DB_PATH, POSTS_DB_PATH, PROFILE_PATH


def section(title: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {title}")
    print("=" * 50)


def check_file(label: str, path: Path) -> bool:
    exists = path.exists()
    size = f"{path.stat().st_size:,} bytes" if exists else "—"
    status = "OK" if exists else "MISSING"
    print(f"  [{status}] {label}: {path}  ({size})")
    return exists


def check_sqlite(label: str, path: Path, queries: list[tuple[str, str]]) -> None:
    if not path.exists():
        print(f"  [SKIP] {label}: file not found")
        return
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        for description, sql in queries:
            row = conn.execute(sql).fetchone()
            value = row[0] if row else 0
            print(f"  {description}: {value}")
        conn.close()
    except Exception as e:
        print(f"  [ERROR] {label}: {e}")


def check_chroma() -> None:
    if not CHROMA_DIR.exists():
        print(f"  [MISSING] {CHROMA_DIR}")
        return
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        collections = client.list_collections()
        if not collections:
            print("  [WARN] No collections found in ChromaDB")
            return
        for col in collections:
            count = col.count()
            print(f"  Collection '{col.name}': {count:,} chunks")
    except Exception as e:
        print(f"  [ERROR] ChromaDB: {e}")


def main() -> None:
    print("\nContendo — Data Verification")
    print(f"DATA_DIR = {os.environ.get('DATA_DIR', '(not set, using default)')}")

    section("File existence")
    check_file("chroma_db dir", CHROMA_DIR)
    check_file("posts.db     ", POSTS_DB_PATH)
    check_file("hierarchy.db ", HIERARCHY_DB_PATH)
    check_file("profile.json ", PROFILE_PATH)

    section("ChromaDB collections")
    check_chroma()

    section("posts.db stats")
    check_sqlite(
        "posts.db",
        POSTS_DB_PATH,
        [
            ("  Total posts   ", "SELECT COUNT(*) FROM posts"),
            ("  Total versions", "SELECT COUNT(*) FROM post_versions"),
        ],
    )

    section("hierarchy.db stats")
    check_sqlite(
        "hierarchy.db",
        HIERARCHY_DB_PATH,
        [
            ("  Source nodes", "SELECT COUNT(*) FROM source_nodes"),
            ("  Topic nodes ", "SELECT COUNT(*) FROM topic_nodes"),
        ],
    )

    print("\nDone.\n")


if __name__ == "__main__":
    main()
