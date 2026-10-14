"""Publishing endpoints: connected accounts, publish jobs, and the provider's
webhook. No endpoint here publishes: jobs are queued and the worker sends them.

Handlers are plain functions (not async), so FastAPI runs them in its
threadpool and a slow provider call never blocks the server.
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from auth.supabase_jwt import get_user_id_dep
from billing import gates
from memory import publish_store
from memory.feedback_store import post_owned_by
from publishing import rules, service
from publishing.jobs import apply_status
from publishing.provider import PublishingConfigError, PublishingProvider, get_provider
from publishing.types import Platform, ProviderError

logger = logging.getLogger(__name__)

router = APIRouter()

_UNAVAILABLE = "Publishing isn't available right now. Please try again later."
_MAX_MEDIA_BYTES = 50 * 1024 * 1024
# Where a user lands after connecting an account at the provider.
_CONNECT_RETURN_PATH = "/settings/accounts"


def _provider() -> PublishingProvider:
    try:
        return get_provider()
    except PublishingConfigError:
        logger.error("publishing is not configured")
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)


def _provider_failed(route: str, error: ProviderError) -> HTTPException:
    logger.error("%s: provider error %s: %s", route, error.code.value, error)
    return HTTPException(status_code=502, detail=_UNAVAILABLE)


def _account_view(row: dict) -> dict:
    return {
        "id": row["id"],
        "platform": row["platform"],
        "label": rules.label(row["platform"]),
        "display_name": row["display_name"],
        "status": row["status"],
    }


def _job_view(row: dict) -> dict:
    results = row.get("results") or []
    failed = next((r for r in results if r.get("error_code")), None)
    return {
        "id": row["id"],
        "post_id": row.get("post_id"),
        "content": row["content"],
        "account_ids": row["account_ids"],
        "status": row["status"],
        "scheduled_at": row.get("scheduled_at"),
        "published_at": row.get("published_at"),
        "created_at": row.get("created_at"),
        "results": [
            {"account_id": r.get("account_id"), "platform": r.get("platform"), "status": r.get("status"),
             "url": r.get("url") or "", "message": rules.user_message(r.get("error_code"), r.get("platform"))}
            for r in results
        ],
        # What the user should do, never the provider's own error text.
        "message": rules.user_message(row.get("error_code"), failed.get("platform") if failed else None),
        "error_code": row.get("error_code"),
    }


@router.get("/publishing/platforms")
def list_platforms(user_id: str = Depends(get_user_id_dep)) -> dict:
    return {"platforms": rules.preview()}


@router.get("/publishing/accounts")
def list_accounts(user_id: str = Depends(get_user_id_dep)) -> dict:
    provider = _provider()
    try:
        rows = service.refresh_accounts(user_id, provider)
    except ProviderError as error:
        # Show what we last knew rather than nothing.
        logger.warning("GET /publishing/accounts: refresh failed: %s", error)
        rows = publish_store.list_accounts(user_id, provider.name)
    return {"accounts": [_account_view(row) for row in rows]}


class ConnectRequest(BaseModel):
    platform: Platform


@router.post("/publishing/connect")
def connect_account(req: ConnectRequest, user_id: str = Depends(get_user_id_dep)) -> dict:
    """A URL to send the user to, to connect one account on this platform."""
    provider = _provider()
    gates.require_account_slot(user_id, len(publish_store.list_accounts(user_id, provider.name)))
    origin = os.environ.get("FRONTEND_ORIGIN", "").strip().rstrip("/")
    if not origin:
        logger.error("POST /publishing/connect: FRONTEND_ORIGIN is not set")
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    try:
        ref = service.ensure_end_user(user_id, provider)
        return {"url": provider.get_connect_url(ref, req.platform, f"{origin}{_CONNECT_RETURN_PATH}")}
    except ProviderError as error:
        raise _provider_failed("POST /publishing/connect", error)


@router.delete("/publishing/accounts/{account_id}")
def disconnect_account(account_id: str, user_id: str = Depends(get_user_id_dep)) -> dict:
    """Always allowed, whatever the plan: a user can remove our access at any time."""
    provider = _provider()
    try:
        if not service.disconnect(user_id, account_id, provider):
            raise HTTPException(status_code=404, detail="Account not found")
    except ProviderError as error:
        raise _provider_failed("DELETE /publishing/accounts", error)
    return {"disconnected": True}


@router.post("/publishing/media")
def upload_media(file: UploadFile = File(...), user_id: str = Depends(get_user_id_dep)) -> dict:
    provider = _provider()
    gates.require_publishing(user_id)
    content_type = file.content_type or ""
    if not content_type.startswith(("image/", "video/")):
        raise HTTPException(status_code=422, detail="Upload an image or a video.")
    data = file.file.read(_MAX_MEDIA_BYTES + 1)
    if len(data) > _MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large. The limit is 50 MB.")
    try:
        ref = service.ensure_end_user(user_id, provider)
        item = provider.upload_media(ref, file.filename or "upload", content_type, data)
    except ProviderError as error:
        raise _provider_failed("POST /publishing/media", error)
    return {"ref": item.ref, "kind": item.kind}


class MediaRef(BaseModel):
    ref: str = Field(min_length=1, max_length=2000)
    kind: str = Field(pattern="^(image|video)$")


class CreateJobRequest(BaseModel):
    content: str = Field(max_length=70_000)
    account_ids: list[str] = Field(max_length=20)
    post_id: int | None = None
    media: list[MediaRef] = Field(default_factory=list, max_length=10)
    when: str = Field(pattern="^(now|schedule|queue)$")
    # For when="schedule": an ISO 8601 time with its UTC offset.
    scheduled_at: datetime | None = None
    # The user's IANA time zone, for when="queue".
    timezone: str = "UTC"


@router.post("/publishing/jobs")
def create_job(req: CreateJobRequest, user_id: str = Depends(get_user_id_dep)) -> dict:
    provider = _provider()
    gates.require_publishing(user_id)
    if req.post_id is not None and not post_owned_by(req.post_id, user_id):
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        job = service.create_job(
            user_id, provider,
            content=req.content, account_ids=req.account_ids, post_id=req.post_id,
            media=[item.model_dump() for item in req.media],
            when=req.when, scheduled_at=req.scheduled_at, tz_name=req.timezone,
        )
    except service.PublishRequestError as error:
        raise HTTPException(status_code=422, detail={"code": "cannot_publish", "problems": error.problems})
    return {"job": _job_view(job)}


@router.get("/publishing/jobs")
def list_jobs(user_id: str = Depends(get_user_id_dep)) -> dict:
    return {"jobs": [_job_view(row) for row in publish_store.list_jobs(user_id)]}


@router.post("/publishing/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user_id: str = Depends(get_user_id_dep)) -> dict:
    job = publish_store.cancel_job(user_id, job_id)
    if job is None:
        if publish_store.get_job(user_id, job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=409, detail="This post has already gone out or is on its way, so it can't be cancelled.")
    return {"job": _job_view(job)}


def _apply_webhook(provider: PublishingProvider, body: bytes, headers: dict[str, str]) -> str:
    update = provider.parse_webhook(body, headers)
    if update is None:
        return "ignored"
    job = publish_store.get_job_by_provider_ref(provider.name, update.provider_post_ref)
    if job is None:
        return "unknown_post"
    apply_status(job, update.status, publish_store.list_accounts(job["user_id"], provider.name))
    return "applied"


@router.post("/publishing/webhook")
async def provider_webhook(request: Request) -> dict:
    """Public, and trusted only through the provider's signature over the raw body."""
    provider = _provider()
    body = await request.body()
    headers = {name.lower(): value for name, value in request.headers.items()}
    try:
        outcome = await run_in_threadpool(_apply_webhook, provider, body, headers)
    except PermissionError:
        logger.warning("POST /publishing/webhook: signature rejected")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        logger.exception("POST /publishing/webhook failed")
        raise HTTPException(status_code=500, detail="Webhook handling failed")
    return {"received": True, "outcome": outcome}
