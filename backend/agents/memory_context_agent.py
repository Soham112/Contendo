"""memory_context for an ingested source: one Haiku call, after a deterministic
check against the user's experience nodes.

Retired by the provenance work (step 3.3): once frames read `authorship`,
memory_context only says which part of the author's life their own text is from.
"""
import logging

from llm.client import HAIKU, complete
from memory.entity_store import _normalize_entity_name

logger = logging.getLogger(__name__)

CONTEXT_CLASSIFY_SYSTEM_PROMPT = """You are a context classifier. Given a short passage of text, determine which of four memory contexts it belongs to.

Contexts:
- "work"             — professional work: team projects, client work, production systems, sprints, company context
- "personal_project" — personal side projects, experiments, weekend builds, indie work
- "learning"         — external knowledge: articles, research, books, courses, videos, things the user read or watched
- "observation"      — patterns the user has noticed, meta-commentary, "I keep seeing", "most teams I talk to"

Key signals:
- "we built", "our team", "the client", "production", "sprint", "my company" → work
- "I built", "my side project", "I was experimenting", "over the weekend", "my own" → personal_project
- "the article argues", "research shows", "according to", "I read", "the author", "studies show" → learning
- "I keep seeing", "I've noticed", "the pattern I notice", "most teams", "in my experience observing" → observation

Return ONLY one of: "work", "personal_project", "learning", "observation"
No explanation, no punctuation, just the single label."""

VALID_MEMORY_CONTEXTS = {"work", "personal_project", "learning", "observation"}


def classify_memory_context(text: str, *, user_id: str) -> str:
    """Classify text into a memory context using Claude Haiku language pattern detection.

    Uses first 200 words. Returns one of: "work" | "personal_project" |
    "learning" | "observation". Defaults to "learning" on any failure.

    Called at ingest time when the user has not explicitly set memory_context,
    and also via the /suggest-memory-context endpoint for UI pre-selection.
    """
    preview = " ".join(text.split()[:200])
    try:
        message = complete(
            model=HAIKU,
            max_tokens=10,
            system=CONTEXT_CLASSIFY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": preview}],
            user_id=user_id,
            event_type="memory_context_classify",
        )
        result = message.content[0].text.strip().lower().strip('"\'')
        if result in VALID_MEMORY_CONTEXTS:
            return result
    except Exception as e:
        logger.warning("memory context classification failed: %s", e)
    return "learning"


def crossref_experience_context(text: str, user_id: str) -> str | None:
    """Check if text mentions known experience entities and return a suggested context.

    Loads experience_nodes for the user and checks if any entity_name appears
    in the text. If a work node matches → "work". If a personal_project node
    matches → "personal_project". Returns None when no match found, so the
    caller can fall back to the Haiku classifier.

    Designed to be fast: one DB read + string matching, no LLM call.
    """
    try:
        from memory.experience_store import get_experience_nodes
        nodes = get_experience_nodes(user_id)
        if not nodes:
            return None
        text_lower = text.lower()
        work_match = False
        project_match = False
        for node in nodes:
            name = _normalize_entity_name(node.get("entity_name", ""))
            if not name or len(name) < 3:
                continue
            if name in text_lower:
                if node["node_type"] == "work":
                    work_match = True
                elif node["node_type"] == "personal_project":
                    project_match = True
        # work takes precedence over personal_project when both match
        if work_match:
            return "work"
        if project_match:
            return "personal_project"
    except Exception as e:
        logger.debug("experience cross-reference failed: %s", e)
    return None
