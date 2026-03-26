from fastapi import APIRouter, Query

from agents.ideation_agent import generate_suggestions

router = APIRouter()


@router.get("/suggestions")
async def suggestions(
    count: int = Query(default=8, ge=1, le=15),
    topic: str | None = Query(default=None),
) -> dict:
    ideas = generate_suggestions(count=count, topic=topic)
    return {"suggestions": ideas}
