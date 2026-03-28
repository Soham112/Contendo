import logging

from fastapi import APIRouter, Depends, HTTPException

from auth.clerk import get_user_id_dep
from memory.profile_store import load_profile, profile_exists, save_profile

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile")
async def get_profile(user_id: str = Depends(get_user_id_dep)) -> dict:
    logger.info(f"GET /profile for user_id={user_id}")
    exists = profile_exists(user_id)
    profile = load_profile(user_id=user_id)
    logger.info(f"GET /profile: has_profile={exists}, name={profile.get('name', '')!r} for user_id={user_id}")
    return {"profile": profile, "has_profile": exists}


@router.post("/profile")
async def post_profile(
    profile: dict,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    logger.info(f"POST /profile for user_id={user_id}, name={profile.get('name', '')!r}")
    save_profile(profile, user_id=user_id)

    # Read back immediately to verify the write landed on disk
    saved = load_profile(user_id=user_id)
    if not saved.get("name", "").strip() == profile.get("name", "").strip():
        logger.error(
            f"POST /profile: save verification FAILED for user_id={user_id} "
            f"(wrote name={profile.get('name')!r}, read back name={saved.get('name')!r})"
        )
        raise HTTPException(status_code=500, detail="Profile save verification failed")

    logger.info(f"POST /profile: saved and verified for user_id={user_id}")
    return {"saved": True, "user_id": user_id}
