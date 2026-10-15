import logging
from uuid import UUID

from anthropic import APIStatusError, InternalServerError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents.ingestion_agent import ingest_content
from agents.refine_agent import MISSING_SOURCES_MESSAGE, MissingRefineSources, refine_selection
from agents.scorer_agent import score_text
from agents.visual_agent import generate_visuals, generate_svg_for_diagram
from auth.supabase_jwt import get_user_id_dep
from billing.entitlements import get_entitlements
from billing.gates import quota_exceeded
from config import features
from memory import billing_store
from memory.account_store import get_account
from pipeline.graph import run_pipeline
from utils.business_notes import details_note, find_pillar

logger = logging.getLogger(__name__)

router = APIRouter()

_GENERIC_500 = "Something went wrong. Please try again."
_SCORE_FAILED = "Couldn't score this post. Try again."

# Request size bounds for /refine-selection: far above any real post or
# instruction, low enough that one request can't carry an arbitrarily large prompt.
_MAX_POST_CHARS = 30_000
_MAX_INSTRUCTION_CHARS = 2_000
# The details a business user gives for one post (a listing, a sale, an event).
_MAX_DETAILS_CHARS = 4_000


class GenerateRequest(BaseModel):
    topic: str
    format: str
    tone: str
    # Ignored for a LinkedIn post, whose length the backend sets
    # (utils.formatters.LINKEDIN_RANGE), except under pipeline A, the rollback.
    # The create screen no longer sends it.
    length: str = "standard"
    context: str = ""
    quality: str = "standard"
    # Skip the coverage gate and write an opinion post without specifics.
    no_specifics: bool = False
    # Business users only. pillar: the key of one of their niche's content
    # pillars (GET /niches). pillar_details: what this post is about, in the
    # user's words; saved to their memory as a note before the post is drafted.
    pillar: str | None = None
    pillar_details: str = ""


class ClosestSource(BaseModel):
    title: str
    preview: str
    similarity: float


class ReviewIssue(BaseModel):
    type: str
    sentence_text: str


class RemovedContent(BaseModel):
    # What the review said the removed text mainly was (feeling_or_reaction,
    # motive, fact_or_event, generalisation, ...); None when it had no record.
    kind: str | None
    text: str


class ReviewSummary(BaseModel):
    # clean | fixed | issues_remain | not_reviewed (pipeline.redraft.outcome_node).
    outcome: str
    # The acting issues still on the returned post. Record-only issue types
    # (changed_detail, ai_rhythm) are in the generation trace, never here.
    issues: list[ReviewIssue] = []
    # Content taken out of the post because no source states it. Nothing shows
    # it yet; it is what a later "ask the author" step would ask about.
    removed: list[RemovedContent] = []


class GenerateResponse(BaseModel):
    # "ok", or "low_coverage": the knowledge base doesn't cover the topic, so
    # nothing was drafted (post is ""); see closest_sources and suggestion.
    # Or "draft_truncated": the draft was cut off at its output limit, so no
    # post is returned (post is ""); message says so. Or "draft_refused": the
    # draft model declined to write it; same shape. "draft_empty" means the
    # completed reply contained no usable post. Single-writer pipeline only.
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
    # Single-writer pipeline B only: what its review of the post concluded.
    # None when no review ran (pipeline A or C, or B with quality="draft").
    review: ReviewSummary | None = None


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
    # Missing tracking returns HTTP 409; it is never silently replaced.
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
            detail="Our writing service is overloaded right now. Wait 30 seconds and try again.",
        )
    logger.exception("Anthropic API error")
    raise HTTPException(status_code=500, detail=_GENERIC_500)


def _raise_internal_error(route: str) -> None:
    """Log the active exception and return a generic 500 (never str(e) to the client)."""
    logger.exception("%s failed", route)
    raise HTTPException(status_code=500, detail=_GENERIC_500)


def _release_generation(user_id: str, period: str) -> None:
    """Give back the generation reserved for a request that made no post. A
    failure here is logged, never raised: it must not hide the real outcome."""
    try:
        billing_store.release_generation(user_id, period)
    except Exception:
        logger.exception("could not release a reserved generation for user %s", user_id)


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
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

    pillar = None
    if req.pillar:
        pillar = find_pillar(get_account(user_id), req.pillar)
        if pillar is None:
            raise HTTPException(status_code=400, detail="That kind of post isn't available for your business.")
    details = req.pillar_details.strip()
    if details and pillar is None:
        raise HTTPException(status_code=400, detail="pillar is required with pillar_details")
    if len(details) > _MAX_DETAILS_CHARS:
        raise HTTPException(status_code=400, detail=f"pillar_details is too long (limit {_MAX_DETAILS_CHARS} characters)")

    # One generation is counted before the pipeline runs and given back if it
    # produces no post, so requests in parallel cannot go past the limit.
    entitlements = get_entitlements(user_id)
    period = entitlements.period
    if not await run_in_threadpool(
        billing_store.reserve_generation, user_id, period, entitlements.generation_limit,
    ):
        raise quota_exceeded(entitlements)

    result = None
    try:
        if details:
            # The author's own account of their work, stored as any note is.
            title, note = details_note(pillar, details)
            await run_in_threadpool(
                ingest_content, note, source_type="personal_note", source_title=title,
                user_id=user_id, memory_context="work",
            )
        result = await run_in_threadpool(
            run_pipeline,
            topic=req.topic,
            pillar=pillar.key if pillar else None,
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
    finally:
        if result is None or result.get("status", "ok") != "ok":
            _release_generation(user_id, period)

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
        review=result.get("review"),
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
