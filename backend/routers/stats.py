from fastapi import APIRouter
from pydantic import BaseModel

from memory.vector_store import get_all_tags, get_total_chunks

router = APIRouter()


class StatsResponse(BaseModel):
    total_chunks: int
    tags: list[str]


@router.get("/stats", response_model=StatsResponse)
async def stats() -> StatsResponse:
    return StatsResponse(
        total_chunks=get_total_chunks(user_id="default"),
        tags=get_all_tags(user_id="default"),
    )
