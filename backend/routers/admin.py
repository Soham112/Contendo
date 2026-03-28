# TEMPORARY — admin endpoints for profile migration. Remove after all users are migrated.

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config.paths import PROFILE_PATH, PROFILES_DIR
from memory.profile_store import save_profile

logger = logging.getLogger(__name__)

router = APIRouter()

_MIGRATION_SECRET = os.environ.get("MIGRATION_SECRET", "")


class MigrateRequest(BaseModel):
    target_user_id: str
    profile: Optional[dict[str, Any]] = None  # if provided, use this data directly


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
