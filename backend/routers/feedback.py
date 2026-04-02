import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from config.paths import FEEDBACK_PATH

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    message: str
    page: str


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    entry = {
        "user_id": user_id,
        "message": body.message,
        "page": body.page,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info(f"Feedback received from user={user_id} on page={body.page!r}")
    return {"received": True}
