"""POST /generate/stream: /generate, with the first draft shown as it is written.

The response is server-sent events (read with fetch, since the Supabase token
goes in a header and EventSource cannot send one):

    event: delta   data: {"text": "..."}   settled preview text to append
    event: final   data: the GenerateResponse /generate returns, any status
    event: error   data: {"status_code": 503, "detail": "..."}

A request /generate would reject (400, 401, 402) is rejected the same way,
before the stream starts. Deltas are a preview (utils/draft_preview.py): the
post in `final` is the checked one and replaces it, and a non-ok `final` (no
post) replaces it with nothing. Exactly one `final` or `error` ends the stream.
"""

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from auth.supabase_jwt import get_user_id_dep
from routers.generate import (
    GenerateRequest, generate_response, generation_error, reserve_generation, run_generation,
    validate_generate_request,
)
from utils.draft_preview import DraftPreview

logger = logging.getLogger(__name__)

router = APIRouter()

# Runs whose client went away keep going to the end (the pipeline thread cannot
# be stopped, and its trace and billing must settle); this holds their tasks.
_running: set[asyncio.Task] = set()


def _event(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n"


@router.post("/generate/stream")
async def generate_stream(
    req: GenerateRequest,
    user_id: str = Depends(get_user_id_dep),
) -> StreamingResponse:
    pillar = validate_generate_request(req, user_id)
    period = await reserve_generation(user_id)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    preview = DraftPreview()

    def on_draft_text(delta: str) -> None:   # called in the pipeline's worker thread
        text = preview.feed(delta)
        if text:
            loop.call_soon_threadsafe(queue.put_nowait, ("delta", {"text": text}))

    async def run() -> None:
        try:
            result = await run_generation(req, user_id, pillar, period, on_draft_text)
            outcome = ("final", generate_response(result).model_dump(mode="json"))
        except Exception as e:
            error = generation_error(e, "POST /generate/stream")
            outcome = ("error", {"status_code": error.status_code, "detail": error.detail})
        # Queued after every delta: the worker thread scheduled those before it returned.
        queue.put_nowait(outcome)

    task = asyncio.create_task(run())
    _running.add(task)
    task.add_done_callback(_running.discard)

    async def events() -> AsyncIterator[str]:
        while True:
            kind, data = await queue.get()
            yield _event(kind, data)
            if kind != "delta":
                return

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",   # ask any proxy in front not to buffer the events
    })
