import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from config.paths import FEEDBACK_PATH

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    message: str
    page: str


async def _notify_telegram(user_id: str, page: str, message: str, submitted_at: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram notification skipped — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return
    text = (
        f"🗣 <b>New Feedback</b>\n\n"
        f"<b>From:</b> {user_id}\n"
        f"<b>Page:</b> {page}\n"
        f"<b>Time:</b> {submitted_at}\n\n"
        f"{message}"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as exc:
        logger.warning(f"Telegram notification failed (non-fatal): {exc}")


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    submitted_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "user_id": user_id,
        "message": body.message,
        "page": body.page,
        "submitted_at": submitted_at,
    }
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info(f"Feedback received from user={user_id} on page={body.page!r}")

    asyncio.create_task(
        _notify_telegram(user_id, body.page, body.message, submitted_at)
    )

    return {"received": True}
