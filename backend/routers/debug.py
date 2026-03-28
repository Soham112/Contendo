# TEMPORARY — debug endpoint to verify volume mount and profile paths on Railway.
# Remove once persistence is confirmed working in production.

import os

from fastapi import APIRouter

from config.paths import DATA_DIR, PROFILES_DIR

router = APIRouter()


@router.get("/debug/profile-paths")
async def debug_profile_paths() -> dict:
    """No auth required. Returns path config and directory contents for debugging."""
    profiles_dir_str = str(PROFILES_DIR)
    profiles_dir_exists = os.path.exists(profiles_dir_str)
    return {
        "data_dir": str(DATA_DIR),
        "profiles_dir": profiles_dir_str,
        "profiles_dir_exists": profiles_dir_exists,
        "profile_files": os.listdir(profiles_dir_str) if profiles_dir_exists else [],
        "environment": os.environ.get("ENVIRONMENT", "not set"),
    }
