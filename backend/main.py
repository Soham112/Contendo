import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from anthropic import APIStatusError, InternalServerError
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from agents.ingestion_agent import ingest_content
from utils.file_extractor import extract_text_from_file
from tools.scraper_tool import scrape_url
from tools.obsidian_tool import get_vault_stats, read_vault
from agents.vision_agent import extract_from_image
from agents.ideation_agent import generate_suggestions
from agents.visual_agent import generate_visuals
from agents.humanizer_agent import refine_draft
from agents.scorer_agent import score_text
from memory.vector_store import get_total_chunks, get_all_tags, get_all_sources
from memory.feedback_store import (
    init_db, log_post, get_recent_posts, delete_post, update_post,
    add_version, get_versions, update_latest_version_svg,
)
from pipeline.graph import run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Contendo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / Response Models ---


class IngestRequest(BaseModel):
    content: str = ""
    source_type: str  # "article" | "youtube" | "image" | "note"
    raw_image: str | None = None


class IngestResponse(BaseModel):
    chunks_stored: int
    tags: list[str]


class ScrapeRequest(BaseModel):
    url: str


class ObsidianRequest(BaseModel):
    vault_path: str


class GenerateRequest(BaseModel):
    topic: str
    format: str
    tone: str
    context: str = ""
    quality: str = "standard"


class GenerateResponse(BaseModel):
    post: str
    score: int
    score_feedback: list[str]
    iterations: int


class LogPostRequest(BaseModel):
    topic: str
    format: str
    tone: str
    content: str
    authenticity_score: int
    svg_diagrams: list | None = None


class LogPostResponse(BaseModel):
    post_id: int
    saved: bool


class StatsResponse(BaseModel):
    total_chunks: int
    tags: list[str]


# --- Helpers ---


def _raise_anthropic_error(e: Exception) -> None:
    """Convert Anthropic API errors into appropriate HTTP responses."""
    if isinstance(e, InternalServerError) and "overloaded" in str(e).lower():
        raise HTTPException(
            status_code=503,
            detail="Anthropic API is temporarily overloaded. Wait 30 seconds and try again.",
        )
    raise HTTPException(status_code=500, detail=str(e))


def _feedback_to_instructions(feedback_items: list[str]) -> str:
    """Convert scorer feedback from critique format to action instruction format.

    Prefixes each item with 'ACTION NEEDED:' so Claude treats them as directives
    rather than observations to acknowledge and lightly adjust around.
    """
    if not feedback_items:
        return "Improve the overall flow and make the voice feel more natural and specific."
    instructions = []
    for item in feedback_items:
        item = item.strip().lstrip("—").strip()
        if not item:
            continue
        instructions.append(f"ACTION NEEDED: {item}")
    return "\n\n".join(instructions)


# --- Routes ---


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
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
        result = ingest_content(extracted_text, source_type="image")
    else:
        if not req.content or not req.content.strip():
            raise HTTPException(status_code=400, detail="content is required")
        result = ingest_content(req.content, source_type=req.source_type)

    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"])


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")

    try:
        result = run_pipeline(
            topic=req.topic,
            format=req.format,
            tone=req.tone,
            context=req.context,
            quality=req.quality,
        )
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return GenerateResponse(
        post=result["post"],
        score=result["score"],
        score_feedback=result["score_feedback"],
        iterations=result["iterations"],
    )


@app.post("/log-post", response_model=LogPostResponse)
async def log_post_endpoint(req: LogPostRequest) -> LogPostResponse:
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    post_id = log_post(
        topic=req.topic,
        format=req.format,
        tone=req.tone,
        content=req.content,
        authenticity_score=req.authenticity_score,
        svg_diagrams=json.dumps(req.svg_diagrams) if req.svg_diagrams is not None else None,
    )
    add_version(
        post_id=post_id,
        content=req.content,
        authenticity_score=req.authenticity_score,
        version_type="generated",
    )
    return LogPostResponse(post_id=post_id, saved=True)


@app.get("/history")
async def history() -> dict:
    posts = get_recent_posts(limit=20)
    for post in posts:
        raw = post.get("svg_diagrams")
        post["svg_diagrams"] = json.loads(raw) if raw else None
        versions = get_versions(post["id"])
        for v in versions:
            v["svg_diagrams"] = json.loads(v["svg_diagrams"]) if v.get("svg_diagrams") else None
        post["versions"] = versions
    return {"posts": posts}


@app.get("/library")
async def library() -> dict:
    sources = get_all_sources()
    return {
        "sources": sources,
        "total_chunks": get_total_chunks(),
        "total_sources": len(sources),
    }


@app.get("/suggestions")
async def suggestions(
    count: int = Query(default=8, ge=1, le=15),
    topic: str | None = Query(default=None),
) -> dict:
    ideas = generate_suggestions(count=count, topic=topic)
    return {"suggestions": ideas}


class UpdatePostRequest(BaseModel):
    content: str | None = None
    authenticity_score: int | None = None
    svg_diagrams: list | None = None


@app.patch("/history/{post_id}")
async def update_post_endpoint(post_id: int, req: UpdatePostRequest) -> dict:
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
    updated = update_post(post_id, **kwargs)

    # Versioning side-effects
    if "content" in provided:
        # Refinement: create a new version
        svg_json = kwargs.get("svg_diagrams")
        add_version(
            post_id=post_id,
            content=req.content,
            authenticity_score=req.authenticity_score,
            version_type="refined",
            svg_diagrams=svg_json,
        )
    elif "svg_diagrams" in provided:
        # Diagrams-only update: stamp onto the latest version, no new row
        update_latest_version_svg(post_id, kwargs.get("svg_diagrams"))

    return {"updated": updated}


@app.delete("/history/{post_id}")
async def delete_post_endpoint(post_id: int) -> dict:
    deleted = delete_post(post_id)
    return {"deleted": deleted}


@app.post("/history/{post_id}/restore/{version_id}")
async def restore_version_endpoint(post_id: int, version_id: int) -> dict:
    versions = get_versions(post_id)
    version = next((v for v in versions if v["id"] == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")
    update_post(
        post_id,
        content=version["content"],
        authenticity_score=version["authenticity_score"],
    )
    return {
        "restored": True,
        "version_number": version["version_number"],
        "content": version["content"],
        "authenticity_score": version["authenticity_score"],
    }


class RefineRequest(BaseModel):
    current_draft: str
    refinement_instruction: str


class RefineResponse(BaseModel):
    refined_draft: str
    score: int
    score_feedback: list[str]


class GenerateVisualsRequest(BaseModel):
    post_content: str


@app.post("/refine", response_model=RefineResponse)
async def refine(req: RefineRequest) -> RefineResponse:
    if not req.current_draft.strip():
        raise HTTPException(status_code=400, detail="current_draft is required")
    if not req.refinement_instruction.strip():
        raise HTTPException(status_code=400, detail="refinement_instruction is required")

    processed_instruction = (
        _feedback_to_instructions(req.refinement_instruction.split(". "))
        if req.refinement_instruction
        else ""
    )

    try:
        refined = refine_draft(
            current_draft=req.current_draft,
            refinement_instruction=processed_instruction,
        )
        score, score_feedback = score_text(refined)
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return RefineResponse(
        refined_draft=refined,
        score=score,
        score_feedback=score_feedback,
    )


@app.post("/generate-visuals")
async def generate_visuals_endpoint(req: GenerateVisualsRequest) -> dict:
    if not req.post_content.strip():
        raise HTTPException(status_code=400, detail="post_content is required")
    try:
        visuals = generate_visuals(req.post_content)
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"visuals": visuals}


MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


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


@app.post("/scrape-and-ingest")
async def scrape_and_ingest(req: ScrapeRequest) -> dict:
    try:
        scraped = scrape_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = ingest_content(
        content=scraped["content"],
        source_type="article",
        source_title=scraped["title"],
    )
    return {
        "chunks_stored": result["chunks_stored"],
        "tags": result["tags"],
        "title": scraped["title"],
        "word_count": scraped["word_count"],
    }


@app.post("/ingest-file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)) -> IngestResponse:
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
    result = ingest_content(text, source_type="article", source_title=source_title)
    return IngestResponse(chunks_stored=result["chunks_stored"], tags=result["tags"])


@app.get("/stats", response_model=StatsResponse)
async def stats() -> StatsResponse:
    return StatsResponse(
        total_chunks=get_total_chunks(),
        tags=get_all_tags(),
    )


@app.post("/obsidian/preview")
async def obsidian_preview(req: ObsidianRequest) -> dict:
    try:
        return get_vault_stats(req.vault_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/obsidian/ingest")
async def obsidian_ingest(req: ObsidianRequest) -> dict:
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
