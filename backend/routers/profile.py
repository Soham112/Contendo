from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from memory.profile_store import load_profile, profile_exists, save_profile

router = APIRouter()


@router.get("/profile")
async def get_profile(user_id: str = Depends(get_user_id_dep)) -> dict:
    exists = profile_exists(user_id)
    profile = load_profile(user_id=user_id)
    return {"profile": profile, "has_profile": exists}


@router.post("/profile")
async def post_profile(
    profile: dict,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    save_profile(profile, user_id=user_id)
    return {"saved": True}
