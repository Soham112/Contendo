import logging

from pydantic import BaseModel, Field

from llm.client import SONNET, StructuredOutputError, complete_structured
from pipeline.state import PipelineState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a content authenticity scorer. Score the following post on how much it reads like a real person wrote it: one specific person with a direct voice. Not polished corporate content. Not AI-generated filler. Real.

You cannot see the author's sources, so you cannot know which details are true. Judge how the post is written, never how many details it contains. A post that argues precisely from reasoning, or that shares what the author learned from someone else's work, can score full marks. Never reward a post for containing personal anecdotes, numbers or named examples, and never mark one down for lacking them.

Score across exactly these 5 dimensions, each out of 20 points:

1. Natural voice (0–20): Does it sound like a specific person talking? Does it have personality, opinions, or quirks? Or does it sound like a template?

2. Sentence variety (0–20): Is there rhythm and variation in sentence length? Short punches mixed with longer thoughts? Or is every sentence the same length and structure?

3. Precision (0–20): Does each sentence say something exact that a reader could agree or disagree with? Or does it hedge and deal in vague generalities? Precision is about how claims are stated, not about adding detail.

4. No LLM fingerprints (0–20): Is it free from AI tells? No "In today's world", no "It's worth noting", no perfectly balanced lists of three, no corporate buzzwords, no passive voice chains?

5. Value delivery (0–20): Does the reader get something real — an insight, a lesson, a new way to see something? Or is it fluff?

Also identify up to 3 specific sentences that most hurt the score, and give up to 3 actionable notes.

Rules for the notes: each one says how to rewrite what is already there (tighten, cut, reorder, state more plainly). Never ask the author to add an anecdote, a personal story, an example, a number, a name or any other new detail."""


class DimensionScores(BaseModel):
    natural_voice: int = Field(ge=0, le=20)
    sentence_variety: int = Field(ge=0, le=20)
    precision: int = Field(ge=0, le=20)
    no_llm_fingerprints: int = Field(ge=0, le=20)
    value_delivery: int = Field(ge=0, le=20)


class ScoreResult(BaseModel):
    dimension_scores: DimensionScores
    flagged_sentences: list[str] = Field(default_factory=list, description="Up to 3 sentences that most hurt the score.")
    feedback: list[str] = Field(default_factory=list, description="Up to 3 notes on rewriting what is already there.")


def score_text(draft: str, *, user_id: str) -> tuple[int | None, list[str]]:
    """Score a draft: (total 0-100, feedback + flagged sentences).

    The total is the sum of the five dimension scores, added in code. If the
    scorer does not return a valid result the score is None (and the list is
    empty): there is no placeholder score. API errors propagate.
    """
    try:
        result = complete_structured(
            schema=ScoreResult,
            tool_name="record_score",
            tool_description="Record the scores for this post.",
            model=SONNET,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Score this post:\n\n{draft}"}],
            user_id=user_id,
            event_type="score",
        )
    except StructuredOutputError as exc:
        logger.warning("scorer: no valid score (%s)", exc)
        return None, []

    total = sum(result.dimension_scores.model_dump().values())
    return total, [*result.feedback, *result.flagged_sentences]


def scorer_node(state: PipelineState) -> PipelineState:
    """Score the draft (polished mode). A failed score sets score_error, which
    ends the retry loop: without a score there is nothing to retry towards."""
    if state.get("quality") == "draft":
        state["score"] = 0
        state["score_feedback"] = []
        return state

    score, score_feedback = score_text(state["current_draft"], user_id=state["user_id"])
    state["score_error"] = score is None
    state["score"] = score or 0
    state["score_feedback"] = score_feedback
    state["score_history"] = [
        *state.get("score_history", []),
        {"iteration": state.get("iterations", 0), "score": score, "score_feedback": score_feedback},
    ]
    return state
