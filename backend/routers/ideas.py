from fastapi import APIRouter, Depends, Query

from agents.ideation_agent import generate_suggestions
from auth.clerk import get_user_id_dep

router = APIRouter()


@router.get("/suggestions")
async def suggestions(
    count: int = Query(default=8, ge=1, le=15),
    topic: str | None = Query(default=None),
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    result = generate_suggestions(count=count, topic=topic, user_id=user_id)

    # Sparse KB with no resume — return the signal so the frontend can
    # prompt the user to feed memory before generating ideas.
    if isinstance(result, dict) and result.get("sparse"):
        return result

    return {"suggestions": result}
