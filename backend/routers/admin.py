# TEMPORARY — one-time migration endpoint to copy a legacy profile.json to a
# per-user profile file. Remove after Soham's profile has been migrated.

import logging
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config.paths import PROFILE_PATH, PROFILES_DIR
from memory.profile_store import save_profile

logger = logging.getLogger(__name__)

router = APIRouter()

_MIGRATION_SECRET = os.environ.get("MIGRATION_SECRET", "")


class MigrateRequest(BaseModel):
    target_user_id: str


@router.post("/admin/migrate-profile")
async def migrate_profile(
    body: MigrateRequest,
    x_migration_secret: str = Header(...),
) -> dict:
    """Copies legacy DATA_DIR/profile.json → DATA_DIR/profiles/profile_{target_user_id}.json.

    Protected by x-migration-secret header matching MIGRATION_SECRET env var.
    No Clerk auth required (the user has no profile yet, so auth would fail).
    """
    if not _MIGRATION_SECRET:
        raise HTTPException(status_code=500, detail="MIGRATION_SECRET env var is not set")
    if x_migration_secret != _MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    if not PROFILE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Legacy profile not found at {PROFILE_PATH}",
        )

    import json

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        legacy_profile = json.load(f)

    target_user_id = body.target_user_id.strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id must not be empty")

    os.makedirs(PROFILES_DIR, exist_ok=True)
    save_profile(legacy_profile, user_id=target_user_id)
    dest_path = PROFILES_DIR / f"profile_{target_user_id}.json"

    logger.info(
        f"migrate_profile: copied {PROFILE_PATH} → {dest_path} for user_id={target_user_id}"
    )
    return {
        "migrated": True,
        "from": str(PROFILE_PATH),
        "to": str(dest_path),
        "name": legacy_profile.get("name", ""),
    }
