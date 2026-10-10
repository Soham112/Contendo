import logging
from uuid import UUID

from anthropic import APIStatusError, InternalServerError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents.refine_agent import MISSING_SOURCES_MESSAGE, MissingRefineSources, refine_selection
from agents.scorer_agent import score_text
from agents.visual_agent import generate_visuals, generate_svg_for_diagram
from auth.supabase_jwt import get_user_id_dep
from config import features
from pipeline.graph import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

_GENERIC_500 = "Something went wrong. Please try again."
_SCORE_FAILED = "Couldn't score this post. Try again."

# Request size bounds for /refine-selection: far above any real post or
# instruction, low enough that one request can't carry an arbitrarily large prompt.
_MAX_POST_CHARS = 30_000
_MAX_INSTRUCTION_CHARS = 2_000


class GenerateRequest(BaseModel):
    topic: str
    format: str
    tone: str
    length: str = "standard"
    context: str = ""
    quality: str = "standard"
    # Skip the coverage gate and write an opinion post without specifics.
    no_specifics: bool = False


class ClosestSource(BaseModel):
    title: str
    preview: str
    similarity: float


class GenerateResponse(BaseModel):
    # "ok", or "low_coverage": the knowledge base doesn't cover the topic, so
    # nothing was drafted (post is ""); see closest_sources and suggestion.
    # Or "draft_truncated": the draft was cut off at its output limit, so no
    # post is returned (post is ""); message says so. Single-writer pipeline only.
    status: str = "ok"
    message: str = ""
    post: str
    score: int
    score_feedback: list[str]
    iterations: int
    archetype: str = ""
    scored: bool = False
    retrieval_confidence: str = "medium"
    trace_id: str | None = None  # generation_traces.id; None if the trace write failed
    closest_sources: list[ClosestSource] = []
    suggestion: str = ""
    # Whether the low-coverage notice may offer an opinion post without specifics.
    no_specifics_enabled: bool = False


class ScoreRequest(BaseModel):
    post_content: str


class ScoreResponse(BaseModel):
    # None when the scorer returned no valid result; message then says so.
    score: int | None
    score_feedback: list[str]
    message: str = ""


class RefineSelectionRequest(BaseModel):
    selected_text: str
    instruction: str
    full_post: str
    # Either one locates the post's generation trace (its original sources).
    # Without a trace the rewrite is checked against the post and profile only.
    trace_id: UUID | None = None
    post_id: int | None = None


class RefineSelectionResponse(BaseModel):
    rewritten_text: str
    # "ok", or "reverted": the rewrite kept adding unsupported specifics, so
    # rewritten_text is the selection unchanged and message says why.
    status: str = "ok"
    message: str = ""
    # The model's own note when the instruction asked for something no source has.
    note: str = ""
    sources_used: str = "trace"  # missing tracking returns HTTP 409
    sources_message: str = ""


class GenerateVisualsRequest(BaseModel):
    post_content: str


class RefineVisualRequest(BaseModel):
    svg_code: str
    refinement_instruction: str
    original_description: str
    style_hint: str | None = None


def _raise_anthropic_error(e: Exception) -> None:
    """Convert Anthropic API errors into appropriate HTTP responses."""
    if isinstance(e, InternalServerError) and "overloaded" in str(e).lower():
        raise HTTPException(
            status_code=503,
            detail="Anthropic API is temporarily overloaded. Wait 30 seconds and try again.",
        )
    logger.exception("Anthropic API error")
    raise HTTPException(status_code=500, detail=_GENERIC_500)


def _raise_internal_error(route: str) -> None:
    """Log the active exception and return a generic 500 (never str(e) to the client)."""
    logger.exception("%s failed", route)
    raise HTTPException(status_code=500, detail=_GENERIC_500)


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id_dep),
) -> GenerateResponse:
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
    if req.no_specifics and not features.NO_SPECIFICS_MODE_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Opinion posts without specifics are turned off for now. "
                   "Add a source about this topic, then generate again.",
        )

    try:
        result = await run_in_threadpool(
            run_pipeline,
            topic=req.topic,
            format=req.format,
            tone=req.tone,
            length=req.length,
            context=req.context,
            quality=req.quality,
            user_id=user_id,
            no_specifics=req.no_specifics,
        )
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception:
        _raise_internal_error("POST /generate")

    # Log-only fact check: runs after the response is sent, adds no latency.
    if result.get("fact_check_job"):
        background_tasks.add_task(result["fact_check_job"])

    return GenerateResponse(
        status=result.get("status", "ok"),
        message=result.get("message", ""),
        closest_sources=result.get("closest_sources", []),
        suggestion=result.get("suggestion", ""),
        post=result["post"],
        score=result["score"],
        score_feedback=result["score_feedback"],
        iterations=result["iterations"],
        archetype=result.get("archetype", ""),
        scored=result.get("scored", False),
        retrieval_confidence=result.get("retrieval_confidence", "medium"),
        trace_id=result.get("trace_id"),
        no_specifics_enabled=features.NO_SPECIFICS_MODE_ENABLED,
    )


@router.post("/refine-selection", response_model=RefineSelectionResponse)
async def refine_selection_endpoint(
    req: RefineSelectionRequest,
    user_id: str = Depends(get_user_id_dep),
) -> RefineSelectionResponse:
    """Rewrite one selected passage. The instruction reaches the model unchanged."""
    if not req.selected_text.strip():
        raise HTTPException(status_code=400, detail="selected_text is required")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")
    if not req.full_post.strip():
        raise HTTPException(status_code=400, detail="full_post is required")
    if len(req.full_post) > _MAX_POST_CHARS:
        raise HTTPException(status_code=400, detail=f"full_post is too long (limit {_MAX_POST_CHARS} characters)")
    if len(req.instruction) > _MAX_INSTRUCTION_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"instruction is too long (limit {_MAX_INSTRUCTION_CHARS} characters)",
        )
    if len(req.selected_text) > len(req.full_post):
        raise HTTPException(status_code=400, detail="selected_text cannot be longer than full_post")

    try:
        result = await run_in_threadpool(
            refine_selection,
            selected_text=req.selected_text,
            instruction=req.instruction,
            full_post=req.full_post,
            user_id=user_id,
            trace_id=str(req.trace_id) if req.trace_id else None,
            post_id=req.post_id,
        )
    except MissingRefineSources as exc:
        raise HTTPException(status_code=409, detail={
            "code": "refine_sources_missing", "reason": exc.reason,
            "message": MISSING_SOURCES_MESSAGE,
        }) from None
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception as exc:
        # Exception messages/tracebacks may contain query values or user content.
        logger.error("POST /refine-selection failed category=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=_GENERIC_500) from None
    return RefineSelectionResponse(**result)


@router.post("/score", response_model=ScoreResponse)
async def score(
    req: ScoreRequest,
    user_id: str = Depends(get_user_id_dep),
) -> ScoreResponse:
    if not req.post_content.strip():
        raise HTTPException(status_code=400, detail="post_content is required")
    try:
        s, score_feedback = await run_in_threadpool(score_text, req.post_content, user_id=user_id)
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception:
        _raise_internal_error("POST /score")
    if s is None:
        return ScoreResponse(score=None, score_feedback=[], message=_SCORE_FAILED)
    return ScoreResponse(score=s, score_feedback=score_feedback)


@router.post("/generate-visuals")
async def generate_visuals_endpoint(
    req: GenerateVisualsRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    if not req.post_content.strip():
        raise HTTPException(status_code=400, detail="post_content is required")
    try:
        visuals = await run_in_threadpool(generate_visuals, req.post_content, user_id=user_id)
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception:
        _raise_internal_error("POST /generate-visuals")
    return {"visuals": visuals}


@router.post("/refine-visual")
async def refine_visual_endpoint(
    req: RefineVisualRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    if not req.svg_code.strip():
        raise HTTPException(status_code=400, detail="svg_code is required")
    if not req.refinement_instruction.strip():
        raise HTTPException(status_code=400, detail="refinement_instruction is required")
    try:
        svg_code = await run_in_threadpool(
            generate_svg_for_diagram,
            description=req.original_description,
            style_hint=req.style_hint,
            current_svg=req.svg_code,
            refinement_instruction=req.refinement_instruction,
            user_id=user_id,
        )
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception:
        _raise_internal_error("POST /refine-visual")
    return {"svg_code": svg_code}
