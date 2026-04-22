import os
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from auth.clerk import get_user_id_dep

_IS_PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() == "production"
_OBSIDIAN_DISABLED_MSG = (
    "Obsidian vault ingestion is a local-only feature. "
    "It reads directly from your filesystem and cannot work on a remote server. "
    "Run the backend locally to use this feature."
)

from agents.ingestion_agent import ingest_content
from agents.vision_agent import extract_from_image
from tools.obsidian_tool import (
    extract_vault_from_zip,
    get_vault_stats,
    get_vault_stats_from_dir,
    read_vault,
)
from tools.scraper_tool import scrape_url
from utils.file_extractor import extract_text_from_file

router = APIRouter()

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB


class IngestRequest(BaseModel):
    content: str = ""
    source_type: str  # "article" | "youtube" | "image" | "note" | "personal_note" | "saved_content"
    raw_image: str | None = None
    content_origin: str | None = None  # "personal" | "saved" — only meaningful when source_type is "note"


class IngestResponse(BaseModel):
    chunks_stored: int
    tags: list[str]
    duplicate: bool = False
    message: str = ""


class ScrapeRequest(BaseModel):
    url: str


class ObsidianRequest(BaseModel):
    vault_path: str


def _title_from_text(text: str, filename: str) -> str:
    """Extract a human-readable title from the start of document text.

    Looks for the first newline or sentence boundary within the first 150
    characters. Falls back to the filename stem if the result is too short
    (e.g. a page number or single word on its own line).
    """
    head = text.strip()[:150]

    cuts: list[int] = []
    newline_pos = head.find("\n")
    if newline_pos != -1:
        cuts.append(newline_pos)
    sentence_match = re.search(r"[.!?](?:\s|$)", head)
    if sentence_match:
        cuts.append(sentence_match.start() + 1)  # include the punctuation

    title = head[: min(cuts)].strip() if cuts else head.strip()

    if len(title) < 10:
        title = Path(filename).stem

    return title


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest,
    user_id: str = Depends(get_user_id_dep),
) -> IngestResponse:
    if req.source_type == "image":
        if not req.raw_image:
            raise HTTPException(status_code=400, detail="raw_image is required for image source_type")
        media_type = "image/jpeg"
        if req.raw_image.startswith("data:"):
            header = req.raw_image.split(",")[0]
            if "image/png" in header:
                media_type = "image/png"
            elif "image/webp" in header:
                media_type = "image/webp"
        extracted_text = extract_from_image(req.raw_image, media_type=media_type)
        result = ingest_content(extracted_text, source_type="image", user_id=user_id)
    else:
        if not req.content or not req.content.strip():
            raise HTTPException(status_code=400, detail="content is required")
        # Resolve effective source_type for notes based on content_origin signal.
        # content_origin: "personal" → personal_note (user lived/built it)
        # content_origin: "saved"   → saved_content (external reference saved by user)
        # absent                    → keep as "note" (legacy fallback; treated as saved_content downstream)
        effective_source_type = req.source_type
        if req.source_type == "note" and req.content_origin:
            if req.content_origin == "personal":
                effective_source_type = "personal_note"
            elif req.content_origin == "saved":
                effective_source_type = "saved_content"
        result = ingest_content(req.content, source_type=effective_source_type, user_id=user_id)

    if result.get("duplicate"):
        return IngestResponse(
            chunks_stored=result["chunks_stored"],
            tags=result["tags"],
            duplicate=True,
            message="This content is already in your knowledge base",
        )
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"])


@router.post("/ingest-file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id_dep),
) -> IngestResponse:
    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        text = extract_text_from_file(file.filename or "", raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    source_title = _title_from_text(text, file.filename or "")
    result = ingest_content(text, source_type="article", source_title=source_title, user_id=user_id)
    if result.get("duplicate"):
        return IngestResponse(
            chunks_stored=result["chunks_stored"],
            tags=result["tags"],
            duplicate=True,
            message="This content is already in your knowledge base",
        )
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"])


@router.post("/scrape-and-ingest")
async def scrape_and_ingest(
    req: ScrapeRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    try:
        scraped = scrape_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = ingest_content(
        content=scraped["content"],
        source_type="article",
        source_title=scraped["title"],
        user_id=user_id,
    )
    if result.get("duplicate"):
        return {
            "chunks_stored": result["chunks_stored"],
            "tags": result["tags"],
            "title": scraped["title"],
            "word_count": scraped["word_count"],
            "duplicate": True,
            "message": "This content is already in your knowledge base",
        }
    return {
        "chunks_stored": result["chunks_stored"],
        "tags": result["tags"],
        "title": scraped["title"],
        "word_count": scraped["word_count"],
    }


@router.post("/obsidian/preview")
async def obsidian_preview(req: ObsidianRequest) -> dict:
    if _IS_PRODUCTION:
        raise HTTPException(status_code=400, detail=_OBSIDIAN_DISABLED_MSG)
    try:
        return get_vault_stats(req.vault_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/obsidian/ingest")
async def obsidian_ingest(
    req: ObsidianRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    if _IS_PRODUCTION:
        raise HTTPException(status_code=400, detail=_OBSIDIAN_DISABLED_MSG)
    try:
        notes = list(read_vault(req.vault_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total_chunks = 0
    all_tags: set[str] = set()
    processed = 0

    for note in notes:
        try:
            result = ingest_content(
                content=note["content"],
                source_type="note",
                source_title=note["filename"],
                user_id=user_id,
            )
            total_chunks += result["chunks_stored"]
            all_tags.update(result["tags"])
            processed += 1
        except Exception:
            continue

    return {
        "total_files_processed": processed,
        "total_chunks_stored": total_chunks,
        "total_words_processed": sum(n["word_count"] for n in notes),
        "skipped_files": len(notes) - processed,
        "all_tags": sorted(all_tags),
    }


@router.post("/obsidian/preview-zip")
async def obsidian_preview_zip(
    file: UploadFile = File(...),
) -> dict:
    """Preview an Obsidian vault from a zip file without ingesting it.
    
    Returns vault stats (name, file count, word count, estimated chunks).
    No environment guard — works on both localhost and production.
    """
    raw = await file.read()
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="Zip file exceeds 50 MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded zip file is empty.")
    
    temp_dir = None
    try:
        # Extract zip and get stats
        temp_dir = extract_vault_from_zip(raw)
        stats = get_vault_stats_from_dir(temp_dir)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Clean up temp directory
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/obsidian/ingest-zip")
async def obsidian_ingest_zip(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    """Ingest an Obsidian vault from a zip file into the knowledge base.
    
    Extracts the zip, reads all .md files, and ingests the content.
    No environment guard — works on both localhost and production.
    """
    raw = await file.read()
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="Zip file exceeds 50 MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded zip file is empty.")
    
    temp_dir = None
    try:
        # Extract zip and read vault
        temp_dir = extract_vault_from_zip(raw)
        notes = list(read_vault(temp_dir))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Ingest all notes
    total_chunks = 0
    all_tags: set[str] = set()
    processed = 0

    try:
        for note in notes:
            try:
                result = ingest_content(
                    content=note["content"],
                    source_type="note",
                    source_title=note["filename"],
                    user_id=user_id,
                )
                total_chunks += result["chunks_stored"]
                all_tags.update(result["tags"])
                processed += 1
            except Exception:
                continue
    finally:
        # Clean up temp directory after ingestion completes or fails
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "total_files_processed": processed,
        "total_chunks_stored": total_chunks,
        "total_words_processed": sum(n["word_count"] for n in notes),
        "skipped_files": len(notes) - processed,
        "all_tags": sorted(all_tags),
    }


