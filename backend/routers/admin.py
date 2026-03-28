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
