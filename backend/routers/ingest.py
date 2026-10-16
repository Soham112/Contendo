"""Adding content: notes, images, files, URLs and YouTube videos.

Extraction is in backend/extractors/ (one module per input type); these routes
check for a duplicate, extract, and store through ingest_content.

Duplicates. A file or image with the same bytes (sha256), or a page or video
with the same normalised URL, is already in the library: the route answers at
once, before any paid call. Content whose extracted text is already stored
(content_hash, e.g. a video saved before its URL was recorded) is found after
extraction. Either way the answer names the existing source (title, input type,
date added) with `replaceable: true`, so the frontend can offer to replace it.
Resubmitting with `replace_source_id` re-extracts and replaces that source in
place (unique chunk ids, old content intact until the new one is stored), even
when its text is unchanged: the user chose to refresh it. A replace may only
target the source that has the same file or URL, or, when none has, the same
text (checked after extraction); anything else is a 409.

Language. ingest_content refuses text in a language the embedder can't search
(utils/language.py); every route returns that as a 422 with the message.
"""
import base64
import binascii
import logging
import mimetypes
from typing import Callable, NamedTuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents.ingestion_agent import (ReplaceMismatch, ingest_content, _classify_memory_context,
                                    _crossref_experience_context)
from auth.supabase_jwt import get_user_id_dep
from extractors import Extraction, ExtractionError, ServiceUnavailable
from extractors.file import extract_file
from extractors.image import extract_image
from extractors.url import extract_url, is_valid_url, normalize_url
from extractors import youtube
from memory import source_store
from utils.language import UnsupportedLanguage

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_IMAGE_TYPES = ("image/png", "image/webp")   # anything else is sent as image/jpeg


class IngestRequest(BaseModel):
    content: str = ""
    source_type: str  # "article" | "youtube" | "image" | "note" | "personal_note" | "saved_content"
    raw_image: str | None = None
    content_origin: str | None = None  # "personal" | "saved" — only meaningful when source_type is "note"
    source_title: str | None = None  # optional caller-supplied title for library card display
    memory_context: str | None = None  # "work" | "personal_project" | "learning" | "observation" | None
    video_url: str | None = None  # youtube: saved from the transcript the preview fetched
    replace_source_id: str | None = None  # replace this duplicate (see the module docstring)


class SuggestContextRequest(BaseModel):
    content: str


class IngestResponse(BaseModel):
    chunks_stored: int
    tags: list[str]
    duplicate: bool = False
    message: str = ""
    existing_source_id: str | None = None  # the source a duplicate matched
    existing_title: str | None = None
    existing_type: str | None = None  # its sources.input_type
    existing_added_at: str | None = None  # when it was first added
    replaceable: bool = False  # the user's own source: Replace re-extracts it in place
    title: str | None = None
    word_count: int | None = None


class ScrapeRequest(BaseModel):
    url: str
    replace_source_id: str | None = None


class YouTubeTranscriptRequest(BaseModel):
    url: str


class YouTubeTranscriptResponse(BaseModel):
    transcript: str
    video_id: str
    title: str


_CANT_REPLACE = "This source can't be replaced with different content."


def _already_stored(existing: dict, *, chunks_stored: int = 0, tags: list[str] | None = None) -> IngestResponse:
    return IngestResponse(
        chunks_stored=chunks_stored, tags=tags or [], duplicate=True, replaceable=True,
        existing_source_id=existing["source_id"], existing_title=existing.get("title"),
        existing_type=existing.get("input_type"), existing_added_at=existing.get("created_at"),
        message="This is already in your knowledge base",
    )


def _text_duplicate(result: dict, user_id: str) -> IngestResponse:
    """The answer for content whose text is already stored, naming that source."""
    existing = source_store.get_source(result["duplicate_source_id"], user_id) if result.get("duplicate_source_id") else None
    if existing:
        return _already_stored(existing, chunks_stored=result["chunks_stored"], tags=result["tags"])
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"], duplicate=True,
                          existing_source_id=result.get("duplicate_source_id"),
                          message="This content is already in your knowledge base")


class DuplicateCheck(NamedTuple):
    duplicate: IngestResponse | None = None  # this file or URL is stored: answer now
    replace_by_text: bool = False            # the replace target must have the same text


def _check_duplicate(user_id: str, replace_source_id: str | None, **key) -> DuplicateCheck:
    """Before extraction: an existing source with this file or URL, or for a
    replace, how its target is confirmed. The target is the source with this
    file or URL; when no source has it, the target must have the same text."""
    existing = source_store.find_duplicate(user_id, **key)
    if replace_source_id:
        if existing and existing["source_id"] != replace_source_id:
            raise HTTPException(status_code=409, detail=_CANT_REPLACE)
        return DuplicateCheck(replace_by_text=existing is None)
    return DuplicateCheck(duplicate=_already_stored(existing) if existing else None)


async def _extract(extract: Callable[[], Extraction], error_status: int) -> Extraction:
    try:
        return await run_in_threadpool(extract)
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ExtractionError as e:
        raise HTTPException(status_code=error_status, detail=str(e))


async def _ingest(**kwargs) -> dict:
    """ingest_content in the threadpool. A replace chosen by the user refreshes
    its source even when the text is unchanged."""
    if kwargs.get("replace_source_id"):
        kwargs["refresh_unchanged"] = True
    try:
        return await run_in_threadpool(ingest_content, **kwargs)
    except UnsupportedLanguage as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ReplaceMismatch:
        raise HTTPException(status_code=409, detail=_CANT_REPLACE)


async def _store(extract: Callable[[], Extraction], *, user_id: str, source_type: str, error_status: int,
                 check: DuplicateCheck = DuplicateCheck(), replace_source_id: str | None = None,
                 memory_context: str | None = None) -> IngestResponse:
    extraction = await _extract(extract, error_status)
    result = await _ingest(
        content=extraction.text, source_type=source_type, source_title=extraction.title,
        user_id=user_id, memory_context=memory_context, original=extraction.original,
        replace_source_id=replace_source_id, replace_requires_same_text=check.replace_by_text,
        reported_lang=extraction.metadata.get("lang"),
    )
    if result.get("duplicate"):
        return _text_duplicate(result, user_id)
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"],
                          title=extraction.title, word_count=extraction.metadata.get("word_count"))


def _image_input(raw_image: str) -> tuple[bytes, str]:
    header, _, payload = raw_image.rpartition(",")
    media_type = next((t for t in _IMAGE_TYPES if t in header), "image/jpeg")
    try:
        return base64.b64decode(payload, validate=True), media_type
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="raw_image is not valid base64")


def _note_source_type(req: IngestRequest) -> str:
    """Notes: content_origin (explicit legacy signal), then memory_context
    (own experience → personal_note, learned → saved_content), else note."""
    if req.source_type != "note":
        return req.source_type
    if req.content_origin == "personal":
        return "personal_note"
    if req.content_origin == "saved":
        return "saved_content"
    if req.memory_context in ("work", "personal_project"):
        return "personal_note"
    if req.memory_context in ("learning", "observation"):
        return "saved_content"
    return "note"


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, user_id: str = Depends(get_user_id_dep)) -> IngestResponse:
    if req.source_type == "image":
        if not req.raw_image:
            raise HTTPException(status_code=400, detail="raw_image is required for image source_type")
        data, media_type = _image_input(req.raw_image)
        check = _check_duplicate(user_id, req.replace_source_id, raw_sha256=source_store.bytes_sha256(data))
        if check.duplicate:
            return check.duplicate
        return await _store(lambda: extract_image(data, req.raw_image, media_type, user_id=user_id),
                            user_id=user_id, source_type="image", error_status=422,
                            check=check, replace_source_id=req.replace_source_id)
    if req.source_type == "youtube" and req.video_url:
        vid = youtube.video_id(req.video_url)
        if not vid:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL.")
        check = _check_duplicate(user_id, req.replace_source_id, source_url=youtube.canonical_url(vid))
        if check.duplicate:
            return check.duplicate
        return await _store(lambda: youtube.extract_video(req.video_url), user_id=user_id, source_type="youtube",
                            error_status=422, check=check, replace_source_id=req.replace_source_id,
                            memory_context=req.memory_context)

    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    result = await _ingest(
        content=req.content,
        source_type=_note_source_type(req),
        source_title=req.source_title,
        user_id=user_id,
        memory_context=req.memory_context,
        original=source_store.typed_text(
            "youtube" if req.source_type == "youtube" else "note",   # a transcript pasted by hand
            text=req.content, title_provided=bool(req.source_title),
        ),
        # typed text has no file or URL: a replace target must have the same text
        replace_source_id=req.replace_source_id, replace_requires_same_text=bool(req.replace_source_id),
    )
    if result.get("duplicate"):
        return _text_duplicate(result, user_id)
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"])


@router.post("/suggest-memory-context")
async def suggest_memory_context(req: SuggestContextRequest, user_id: str = Depends(get_user_id_dep)) -> dict:
    """Classify content into a memory context for UI pre-selection.

    Returns {"suggested_context": "work" | "personal_project" | "learning" | "observation"}.
    Experience cross-reference first (deterministic), then the Haiku classifier.
    """
    if not req.content or not req.content.strip():
        return {"suggested_context": "learning"}
    suggested = await run_in_threadpool(_crossref_experience_context, req.content, user_id)
    if not suggested:
        suggested = await run_in_threadpool(_classify_memory_context, req.content, user_id=user_id)
    return {"suggested_context": suggested}


@router.post("/ingest-file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    replace_source_id: str | None = Form(None),
    user_id: str = Depends(get_user_id_dep),
) -> IngestResponse:
    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    check = _check_duplicate(user_id, replace_source_id, raw_sha256=source_store.bytes_sha256(raw))
    if check.duplicate:
        return check.duplicate
    filename = file.filename or ""
    mime = file.content_type or mimetypes.guess_type(filename)[0]
    return await _store(lambda: extract_file(filename, raw, mime), user_id=user_id, source_type="article",
                        error_status=422, check=check, replace_source_id=replace_source_id)


@router.post("/scrape-and-ingest", response_model=IngestResponse)
async def scrape_and_ingest(req: ScrapeRequest, user_id: str = Depends(get_user_id_dep)) -> IngestResponse:
    if not is_valid_url(req.url):
        raise HTTPException(status_code=400, detail="Invalid URL. Please include https:// at the start.")
    check = _check_duplicate(user_id, req.replace_source_id, source_url=normalize_url(req.url))
    if check.duplicate:
        return check.duplicate
    return await _store(lambda: extract_url(req.url), user_id=user_id, source_type="article",
                        error_status=400, check=check, replace_source_id=req.replace_source_id)


@router.post("/fetch-youtube-transcript", response_model=YouTubeTranscriptResponse)
async def fetch_youtube_transcript(req: YouTubeTranscriptRequest,
                                   user_id: str = Depends(get_user_id_dep)) -> YouTubeTranscriptResponse:
    """Preview: fetch the transcript and keep it for the save (extractors/youtube.py)."""
    vid = youtube.video_id(req.url)
    if not vid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL. Supported formats: "
                                                    "youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID")
    extraction = await _extract(lambda: youtube.extract_video(req.url), 422)
    return YouTubeTranscriptResponse(transcript=extraction.text, video_id=vid, title=extraction.title)
