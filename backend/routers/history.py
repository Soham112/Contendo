import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from memory.feedback_store import (
    add_version,
    delete_post,
    get_recent_posts,
    get_versions,
    log_post,
    update_latest_version_svg,
    update_post,
)

router = APIRouter()


class LogPostRequest(BaseModel):
    topic: str
    format: str
    tone: str
    content: str
    authenticity_score: int
    svg_diagrams: list | None = None
    archetype: str = ""


class LogPostResponse(BaseModel):
    post_id: int
    saved: bool


class UpdatePostRequest(BaseModel):
    content: str | None = None
    authenticity_score: int | None = None
    svg_diagrams: list | None = None


@router.get("/history")
async def history(user_id: str = Depends(get_user_id_dep)) -> dict:
    posts = get_recent_posts(user_id=user_id, limit=20)
    for post in posts:
        raw = post.get("svg_diagrams")
        post["svg_diagrams"] = json.loads(raw) if raw else None
        versions = get_versions(post["id"], user_id=user_id)
        for v in versions:
            v["svg_diagrams"] = json.loads(v["svg_diagrams"]) if v.get("svg_diagrams") else None
        post["versions"] = versions
    return {"posts": posts}


@router.post("/log-post", response_model=LogPostResponse)
async def log_post_endpoint(
    req: LogPostRequest,
    user_id: str = Depends(get_user_id_dep),
) -> LogPostResponse:
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    post_id = log_post(
        topic=req.topic,
        format=req.format,
        tone=req.tone,
        content=req.content,
        authenticity_score=req.authenticity_score,
        svg_diagrams=json.dumps(req.svg_diagrams) if req.svg_diagrams is not None else None,
        archetype=req.archetype,
        user_id=user_id,
    )
    add_version(
        post_id=post_id,
        content=req.content,
        authenticity_score=req.authenticity_score,
        version_type="generated",
        user_id=user_id,
    )
    return LogPostResponse(post_id=post_id, saved=True)


@router.patch("/history/{post_id}")
async def update_post_endpoint(
    post_id: int,
    req: UpdatePostRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    provided = req.model_fields_set
    if not provided:
        return {"updated": False}
    kwargs: dict = {}
    if "content" in provided:
        kwargs["content"] = req.content
    if "authenticity_score" in provided:
        kwargs["authenticity_score"] = req.authenticity_score
    if "svg_diagrams" in provided:
        kwargs["svg_diagrams"] = json.dumps(req.svg_diagrams) if req.svg_diagrams is not None else None
    updated = update_post(post_id, user_id=user_id, **kwargs)

    # Versioning side-effects
    if "content" in provided:
        svg_json = kwargs.get("svg_diagrams")
        add_version(
            post_id=post_id,
            content=req.content,
            authenticity_score=req.authenticity_score,
            version_type="refined",
            svg_diagrams=svg_json,
            user_id=user_id,
        )
    elif "svg_diagrams" in provided:
        update_latest_version_svg(post_id, kwargs.get("svg_diagrams"), user_id=user_id)

    return {"updated": updated}


@router.delete("/history/{post_id}")
async def delete_post_endpoint(
    post_id: int,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    deleted = delete_post(post_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": deleted}


@router.post("/history/{post_id}/restore/{version_id}")
async def restore_version_endpoint(
    post_id: int,
    version_id: int,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    versions = get_versions(post_id, user_id=user_id)
    version = next((v for v in versions if v["id"] == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")
    update_post(
        post_id,
        user_id=user_id,
        content=version["content"],
        authenticity_score=version["authenticity_score"],
    )
    return {
        "restored": True,
        "version_number": version["version_number"],
        "content": version["content"],
        "authenticity_score": version["authenticity_score"],
    }
