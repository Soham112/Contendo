from typing import Any, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Inputs
    topic: str
    format: str
    tone: str
    context: Optional[str]
    quality: str  # "draft" | "standard" | "polished" — defaults to "standard" at runtime
    user_id: str  # ChromaDB collection namespace — defaults to "default"; replaced with real user ID when auth is added

    # Loaded profile
    profile: dict[str, Any]

    # Retrieved knowledge
    retrieved_chunks: list[str]       # flat list of "[source_type: X] text" strings — always set for backward compat
    retrieval_bundle: dict            # structured hierarchical bundle {chunks, source_contexts, topic_contexts}
    retrieved_context: str            # pre-formatted text block for draft prompt injection; "" triggers flat fallback

    # Previously posted topics (for novelty injection in draft)
    posted_topics: list[str]

    # Generation state
    current_draft: str
    iterations: int
    archetype: str  # inferred post archetype key, e.g. "incident_report"
    critic_brief: dict  # structured diagnosis from critic_node; {} if skipped (draft mode) or on error

    # Scoring
    score: int
    score_feedback: list[str]

    # Final output
    final_post: str
