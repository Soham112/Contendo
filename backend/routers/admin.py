# TEMPORARY — admin endpoints for profile migration. Remove after all users are migrated.

import json
import logging
import os
import sqlite3
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config.paths import CHROMA_DIR, HIERARCHY_DB_PATH, POSTS_DB_PATH, PROFILE_PATH, PROFILES_DIR
from memory.profile_store import save_profile

logger = logging.getLogger(__name__)

router = APIRouter()

_MIGRATION_SECRET = os.environ.get("MIGRATION_SECRET", "")


class MigrateRequest(BaseModel):
    target_user_id: str
    profile: Optional[dict[str, Any]] = None  # if provided, use this data directly


class MigrateUserDataRequest(BaseModel):
    target_user_id: str


@router.post("/admin/migrate-profile")
async def migrate_profile(
    body: MigrateRequest,
    x_migration_secret: str = Header(...),
) -> dict:
    """Write a profile for any user_id without Clerk auth.

    If body.profile is provided, that data is written directly.
    Otherwise falls back to reading legacy DATA_DIR/profile.json.

    Protected by x-migration-secret header matching MIGRATION_SECRET env var.
    """
    if not _MIGRATION_SECRET:
        raise HTTPException(status_code=500, detail="MIGRATION_SECRET env var is not set")
    if x_migration_secret != _MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    target_user_id = body.target_user_id.strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id must not be empty")

    if body.profile is not None:
        profile_data = body.profile
        source = "request body"
    else:
        if not PROFILE_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Legacy profile not found at {PROFILE_PATH} and no profile provided in body",
            )
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        source = str(PROFILE_PATH)

    os.makedirs(PROFILES_DIR, exist_ok=True)
    save_profile(profile_data, user_id=target_user_id)
    dest_path = PROFILES_DIR / f"profile_{target_user_id}.json"

    logger.info(
        f"migrate_profile: wrote profile for user_id={target_user_id} "
        f"(source={source}, name={profile_data.get('name', '')!r})"
    )
    return {
        "migrated": True,
        "source": source,
        "to": str(dest_path),
        "name": profile_data.get("name", ""),
    }


@router.post("/admin/migrate-user-data")
async def migrate_user_data(
    body: MigrateUserDataRequest,
    x_migration_secret: str = Header(...),
) -> dict:
    """One-time migration: copy all data from user_id='default' to a real Clerk user ID.

    Migrates:
      1. ChromaDB chunks (contendo_default → contendo_{target_user_id})
      2. SQLite posts (posts.db: user_id='default' → target_user_id)
      3. SQLite hierarchy nodes (hierarchy.db: user_id='default' → target_user_id, if column exists)

    contendo_default is preserved as a backup — not deleted.
    Protected by x-migration-secret header.
    """
    if not _MIGRATION_SECRET:
        raise HTTPException(status_code=500, detail="MIGRATION_SECRET env var is not set")
    if x_migration_secret != _MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    target_user_id = body.target_user_id.strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id must not be empty")

    # ── STEP 1: ChromaDB ────────────────────────────────────────────────────
    try:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        try:
            src_collection = chroma_client.get_collection("contendo_default")
        except Exception:
            raise HTTPException(status_code=404, detail="contendo_default not found")

        result = src_collection.get(include=["documents", "metadatas", "embeddings"])
        chunk_ids = result["ids"]
        chunks_migrated = len(chunk_ids)

        if chunks_migrated > 0:
            dst_collection = chroma_client.get_or_create_collection(
                name=f"contendo_{target_user_id}",
                metadata={"hnsw:space": "cosine"},
            )
            dst_collection.upsert(
                ids=chunk_ids,
                documents=result["documents"],
                metadatas=result["metadatas"],
                embeddings=result["embeddings"],
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("migrate_user_data: chromadb step failed")
        raise HTTPException(status_code=500, detail={"step": "chromadb", "error": str(exc)})

    # ── STEP 2: SQLite posts ────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(str(POSTS_DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "UPDATE posts SET user_id = ? WHERE user_id = 'default'",
            (target_user_id,),
        )
        rows_updated = cur.rowcount
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.exception("migrate_user_data: posts step failed")
        raise HTTPException(status_code=500, detail={"step": "posts", "error": str(exc)})

    # ── STEP 3: SQLite hierarchy ────────────────────────────────────────────
    hierarchy_result: str
    try:
        conn = sqlite3.connect(str(HIERARCHY_DB_PATH))
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(source_nodes)")
        columns = [row[1] for row in cur.fetchall()]

        if "user_id" in columns:
            cur.execute(
                "UPDATE source_nodes SET user_id = ? WHERE user_id = 'default'",
                (target_user_id,),
            )
            source_nodes_updated = cur.rowcount
            cur.execute(
                "UPDATE topic_nodes SET user_id = ? WHERE user_id = 'default'",
                (target_user_id,),
            )
            topic_nodes_updated = cur.rowcount
            nodes_migrated = source_nodes_updated + topic_nodes_updated
            hierarchy_result = f"{nodes_migrated} nodes migrated"
        else:
            hierarchy_result = "skipped - no user_id column in hierarchy tables"

        conn.commit()
        conn.close()
    except Exception as exc:
        logger.exception("migrate_user_data: hierarchy step failed")
        raise HTTPException(status_code=500, detail={"step": "hierarchy", "error": str(exc)})

    logger.info(
        f"migrate_user_data: target={target_user_id}, "
        f"chunks={chunks_migrated}, posts={rows_updated}, hierarchy={hierarchy_result}"
    )
    return {
        "migrated": True,
        "target_user_id": target_user_id,
        "chunks_migrated": chunks_migrated,
        "posts_migrated": rows_updated,
        "hierarchy": hierarchy_result,
        "note": (
            "contendo_default collection preserved as backup. "
            "Profile migration is separate — run /admin/migrate-profile too."
        ),
    }


class MigrateToSupabaseRequest(BaseModel):
    old_clerk_id: str
    new_supabase_id: str


@router.post("/admin/migrate-to-supabase")
async def migrate_to_supabase(
    body: MigrateToSupabaseRequest,
    x_migration_secret: str = Header(...),
) -> dict:
    """Migrate a user's profile, posts, and post_versions from local files/SQLite to Supabase.

    Request body:
      old_clerk_id: The old Clerk user ID (e.g. user_3BYsinXXXX) to read from DATA_DIR
      new_supabase_id: The new Supabase user ID (UUID) to write to

    Protected by x-migration-secret header matching MIGRATION_SECRET env var.

    Migrates:
      1. Profile: DATA_DIR/profiles/profile_{old_clerk_id}.json → Supabase profiles table
      2. Posts: posts.db WHERE user_id = old_clerk_id → Supabase posts table
      3. Post versions: post_versions for migrated posts → Supabase post_versions table

    Returns counts of what was migrated.
    """
    if not _MIGRATION_SECRET:
        raise HTTPException(status_code=500, detail="MIGRATION_SECRET env var is not set")
    if x_migration_secret != _MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    old_clerk_id = body.old_clerk_id.strip()
    new_supabase_id = body.new_supabase_id.strip()

    if not old_clerk_id:
        raise HTTPException(status_code=400, detail="old_clerk_id must not be empty")
    if not new_supabase_id:
        raise HTTPException(status_code=400, detail="new_supabase_id must not be empty")

    # ── STEP 1: Migrate Profile ─────────────────────────────────────────
    profile_migrated = False
    try:
        profile_path = PROFILES_DIR / f"profile_{old_clerk_id}.json"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
            from db.supabase_client import supabase
            supabase.table("profiles").upsert({
                "id": new_supabase_id,
                "data": profile_data,
            }).execute()
            profile_migrated = True
            logger.info(f"migrate_to_supabase: profile migrated for {new_supabase_id} from {profile_path}")
        else:
            logger.info(f"migrate_to_supabase: profile not found at {profile_path}, skipping")
    except Exception as exc:
        logger.exception(f"migrate_to_supabase: profile migration failed for {old_clerk_id}")
        raise HTTPException(status_code=500, detail=f"Profile migration failed: {str(exc)}")

    # ── STEP 2: Migrate Posts ───────────────────────────────────────────
    posts_migrated = 0
    post_versions_migrated = 0
    id_map: dict[int, int] = {}

    try:
        if POSTS_DB_PATH.exists():
            conn = sqlite3.connect(str(POSTS_DB_PATH))
            conn.row_factory = sqlite3.Row

            posts = conn.execute(
                "SELECT * FROM posts WHERE user_id = ?",
                (old_clerk_id,),
            ).fetchall()

            if posts:
                from db.supabase_client import supabase
                for post in posts:
                    row = dict(post)
                    old_post_id = row.pop("id")
                    row["user_id"] = new_supabase_id
                    # Filter out None values except svg_diagrams (which can be null but is valid)
                    row = {k: v for k, v in row.items() if v is not None or k == "svg_diagrams"}
                    result = supabase.table("posts").insert(row).execute()
                    if result.data:
                        new_post_id = result.data[0]["id"]
                        id_map[old_post_id] = new_post_id
                        posts_migrated += 1

                logger.info(f"migrate_to_supabase: {posts_migrated} posts migrated for {new_supabase_id}")

                # ── STEP 3: Migrate Post Versions ───────────────────────────────────
                if id_map:
                    placeholders = ",".join("?" * len(id_map))
                    versions = conn.execute(
                        f"SELECT * FROM post_versions WHERE post_id IN ({placeholders})",
                        list(id_map.keys()),
                    ).fetchall()

                    if versions:
                        from db.supabase_client import supabase
                        for v in versions:
                            v_row = dict(v)
                            v_row.pop("id")  # let Supabase generate new id
                            old_version_post_id = v_row["post_id"]
                            v_row["post_id"] = id_map.get(old_version_post_id, old_version_post_id)
                            v_row = {k: v for k, v in v_row.items() if v is not None or k == "svg_diagrams"}
                            result = supabase.table("post_versions").insert(v_row).execute()
                            if result.data:
                                post_versions_migrated += 1

                        logger.info(f"migrate_to_supabase: {post_versions_migrated} post_versions migrated for {new_supabase_id}")

            conn.close()
        else:
            logger.info(f"migrate_to_supabase: posts.db not found at {POSTS_DB_PATH}, skipping posts migration")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"migrate_to_supabase: posts migration failed for {old_clerk_id}")
        raise HTTPException(status_code=500, detail=f"Posts migration failed: {str(exc)}")

    logger.info(
        f"migrate_to_supabase: completed for {old_clerk_id} → {new_supabase_id} "
        f"(profile={profile_migrated}, posts={posts_migrated}, versions={post_versions_migrated})"
    )
    return {
        "migrated": True,
        "old_clerk_id": old_clerk_id,
        "new_supabase_id": new_supabase_id,
        "profile_migrated": profile_migrated,
        "posts_migrated": posts_migrated,
        "post_versions_migrated": post_versions_migrated,
    }
