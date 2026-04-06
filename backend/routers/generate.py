from anthropic import APIStatusError, InternalServerError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.humanizer_agent import refine_draft
from agents.scorer_agent import score_text
from agents.visual_agent import generate_visuals
from auth.clerk import get_user_id_dep
from pipeline.graph import run_pipeline

router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str
    format: str
    tone: str
    length: str = "standard"
    context: str = ""
    quality: str = "standard"


class GenerateResponse(BaseModel):
    post: str
    score: int
    score_feedback: list[str]
    iterations: int
    archetype: str = ""
    scored: bool = False
    retrieval_confidence: str = "medium"


class ScoreRequest(BaseModel):
    post_content: str


class ScoreResponse(BaseModel):
    score: int
    score_feedback: list[str]


class RefineRequest(BaseModel):
    current_draft: str
    refinement_instruction: str


class RefineResponse(BaseModel):
    refined_draft: str
    score: int
    score_feedback: list[str]


class RefineSelectionRequest(BaseModel):
    selected_text: str
    instruction: str
    full_post: str


class GenerateVisualsRequest(BaseModel):
    post_content: str


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


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    user_id: str = Depends(get_user_id_dep),
) -> GenerateResponse:
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")

    try:
        result = run_pipeline(
            topic=req.topic,
            format=req.format,
            tone=req.tone,
            length=req.length,
            context=req.context,
            quality=req.quality,
            user_id=user_id,
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
        archetype=result.get("archetype", ""),
        scored=result.get("scored", False),
        retrieval_confidence=result.get("retrieval_confidence", "medium"),
    )


@router.post("/refine", response_model=RefineResponse)
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


@router.post("/refine-selection")
async def refine_selection(
    req: RefineSelectionRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    from agents.humanizer_agent import refine_selection as refine_selection_fn

    rewritten = await refine_selection_fn(
        selected_text=req.selected_text,
        instruction=req.instruction,
        full_post=req.full_post,
        user_id=user_id,
    )
    return {"rewritten_text": rewritten}


@router.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    if not req.post_content.strip():
        raise HTTPException(status_code=400, detail="post_content is required")
    try:
        s, score_feedback = score_text(req.post_content)
    except (InternalServerError, APIStatusError) as e:
        _raise_anthropic_error(e)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ScoreResponse(score=s, score_feedback=score_feedback)


@router.post("/generate-visuals")
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
