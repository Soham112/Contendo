import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from agents.ingestion_agent import ingest_content
from agents.vision_agent import extract_from_image
from agents.ideation_agent import generate_suggestions
from agents.visual_agent import generate_visuals
from agents.humanizer_agent import refine_draft
from agents.scorer_agent import score_text
from memory.vector_store import get_total_chunks, get_all_tags, get_all_sources
from memory.feedback_store import init_db, log_post, get_recent_posts
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


class GenerateRequest(BaseModel):
    topic: str
    format: str
    tone: str
    context: str = ""


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

    result = run_pipeline(
        topic=req.topic,
        format=req.format,
        tone=req.tone,
        context=req.context,
    )

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
    return LogPostResponse(post_id=post_id, saved=True)


@app.get("/history")
async def history() -> dict:
    posts = get_recent_posts(limit=20)
    for post in posts:
        raw = post.get("svg_diagrams")
        post["svg_diagrams"] = json.loads(raw) if raw else None
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
async def suggestions(count: int = Query(default=8, ge=1, le=10)) -> dict:
    ideas = generate_suggestions(count=count)
    return {"suggestions": ideas}


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

    refined = refine_draft(req.current_draft, req.refinement_instruction)
    score, score_feedback = score_text(refined)

    return RefineResponse(
        refined_draft=refined,
        score=score,
        score_feedback=score_feedback,
    )


@app.post("/generate-visuals")
async def generate_visuals_endpoint(req: GenerateVisualsRequest) -> dict:
    if not req.post_content.strip():
        raise HTTPException(status_code=400, detail="post_content is required")
    visuals = generate_visuals(req.post_content)
    return {"visuals": visuals}


@app.get("/stats", response_model=StatsResponse)
async def stats() -> StatsResponse:
    return StatsResponse(
        total_chunks=get_total_chunks(),
        tags=get_all_tags(),
    )
