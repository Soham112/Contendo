"""A 2-3 sentence summary of an ingested source, for its source node: one Haiku call."""
import logging

from llm.client import HAIKU, complete

logger = logging.getLogger(__name__)


def generate_source_summary(content: str, *, user_id: str) -> str:
    """Generate a 2-3 sentence summary of the source via Claude Haiku.

    Uses first 700 words of content. Returns "" on any failure — never
    blocks ingestion.
    """
    preview = " ".join(content.split()[:700])
    try:
        message = complete(
            model=HAIKU,
            max_tokens=120,
            system="You are a summarization assistant. Summarize the provided text in 2-3 concise sentences that capture the key ideas. Return only the summary, no preamble.",
            messages=[{"role": "user", "content": f"Summarize this:\n\n{preview}"}],
            user_id=user_id,
            event_type="ingest_summary",
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.warning("source summary generation failed: %s", e)
        return ""
