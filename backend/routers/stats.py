from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from memory.vector_store import get_all_tags, get_total_chunks

router = APIRouter()


class StatsResponse(BaseModel):
    total_chunks: int
    tags: list[str]


@router.get("/stats", response_model=StatsResponse)
async def stats(user_id: str = Depends(get_user_id_dep)) -> StatsResponse:
    return StatsResponse(
        total_chunks=get_total_chunks(user_id=user_id),
        tags=get_all_tags(user_id=user_id),
    )
