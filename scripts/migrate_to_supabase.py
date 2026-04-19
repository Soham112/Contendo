#!/usr/bin/env python3
"""
One-time migration: copy a user's data from local SQLite/JSON storage to Supabase.

What it migrates:
  - Profile:       DATA_DIR/profiles/profile_{old_clerk_id}.json  → profiles table
  - Posts:         posts.db WHERE user_id = old_clerk_id           → posts table
  - Post versions: post_versions for migrated posts                → post_versions table

Usage (from project root, with backend venv active and .env loaded):

    python scripts/migrate_to_supabase.py \\
        --old_clerk_id user_3BYsinXXXX \\
        --new_supabase_id a3f2b1c4-0000-0000-0000-000000000000 \\
        --data_dir /data

The script is safe to re-run:
  - Profile is upserted (not inserted), so re-running overwrites cleanly.
  - Posts are inserted fresh; run only once or truncate the Supabase rows first.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from db.supabase_client import supabase  # noqa: E402 — needs env loaded first


def migrate_profile(old_clerk_id: str, new_supabase_id: str, data_dir: Path) -> None:
    profile_path = data_dir / "profiles" / f"profile_{old_clerk_id}.json"
    if not profile_path.exists():
        print(f"  [skip] profile file not found: {profile_path}")
        return
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    supabase.table("profiles").upsert({
        "id": new_supabase_id,
        "data": profile_data,
    }).execute()
    print(f"  [ok] profile upserted for {new_supabase_id}")


def migrate_posts(old_clerk_id: str, new_supabase_id: str, data_dir: Path) -> None:
    db_path = data_dir / "posts.db"
    if not db_path.exists():
        print(f"  [skip] posts.db not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    posts = conn.execute(
        "SELECT * FROM posts WHERE user_id = ?",
        (old_clerk_id,),
    ).fetchall()

    if not posts:
        print(f"  [skip] no posts found for old_clerk_id={old_clerk_id}")
        conn.close()
        return

    print(f"  Found {len(posts)} posts to migrate...")

    # old SQLite id → new Supabase id mapping for version migration
    id_map: dict[int, int] = {}

    for post in posts:
        row = dict(post)
        old_id = row.pop("id")  # let Supabase generate a new id
        row["user_id"] = new_supabase_id  # rewrite owner
        # Strip None-valued keys that Supabase may reject on insert
        row = {k: v for k, v in row.items() if v is not None or k in ("svg_diagrams",)}
        result = supabase.table("posts").insert(row).execute()
        if result.data:
            new_id = result.data[0]["id"]
            id_map[old_id] = new_id
        else:
            print(f"    [warn] failed to insert post old_id={old_id}")

    print(f"  [ok] {len(id_map)}/{len(posts)} posts inserted")

    # ---- post_versions ----
    if not id_map:
        conn.close()
        return

    placeholders = ",".join("?" * len(id_map))
    versions = conn.execute(
        f"SELECT * FROM post_versions WHERE post_id IN ({placeholders})",
        list(id_map.keys()),
    ).fetchall()
    conn.close()

    if not versions:
        print("  [skip] no post_versions found for migrated posts")
        return

    print(f"  Found {len(versions)} post_versions to migrate...")
    version_ok = 0
    for v in versions:
        row = dict(v)
        row.pop("id")  # let Supabase generate a new id
        old_post_id = row["post_id"]
        row["post_id"] = id_map.get(old_post_id, old_post_id)
        row = {k: v for k, v in row.items() if v is not None or k in ("svg_diagrams",)}
        result = supabase.table("post_versions").insert(row).execute()
        if result.data:
            version_ok += 1
        else:
            print(f"    [warn] failed to insert version for post_id={old_post_id}")

    print(f"  [ok] {version_ok}/{len(versions)} post_versions inserted")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate a user's data from local SQLite/JSON to Supabase Postgres."
    )
    parser.add_argument(
        "--old_clerk_id",
        required=True,
        help="Old Clerk user ID (e.g. user_3BYsinXXXX)",
    )
    parser.add_argument(
        "--new_supabase_id",
        required=True,
        help="New Supabase UUID for this user (e.g. a3f2b1c4-...)",
    )
    parser.add_argument(
        "--data_dir",
        default="/data",
        help="Path to Railway /data directory (default: /data)",
    )
    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    print(f"\nMigrating: {args.old_clerk_id!r} → {args.new_supabase_id!r}")
    print(f"Data dir : {data_dir}\n")

    print("── Profile ──────────────────────────────")
    migrate_profile(args.old_clerk_id, args.new_supabase_id, data_dir)

    print("\n── Posts + Versions ─────────────────────")
    migrate_posts(args.old_clerk_id, args.new_supabase_id, data_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
