from typing import Any, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Inputs
    topic: str
    format: str
    tone: str
    context: Optional[str]
    quality: str  # "draft" | "standard" | "polished" — defaults to "standard" at runtime

    # Loaded profile
    profile: dict[str, Any]

    # Retrieved knowledge
    retrieved_chunks: list[str]

    # Previously posted topics (for novelty injection in draft)
    posted_topics: list[str]

    # Generation state
    current_draft: str
    iterations: int

    # Scoring
    score: int
    score_feedback: list[str]

    # Final output
    final_post: str
