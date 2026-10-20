"""Topic tags for an ingested source: one Sonnet call."""
import json

from llm.client import SONNET, complete

TAG_SYSTEM_PROMPT = """You are a tag extraction assistant. Given a passage of text, extract 3–8 short, lowercase topic tags that best describe what this content is about.

Rules:
- Tags must be 1–3 words each
- Use specific, meaningful terms (e.g. "machine learning", "product strategy", "ux research")
- Avoid generic tags like "article", "text", "content", "post"
- Return ONLY a JSON array of strings, nothing else

Example output: ["machine learning", "transformer models", "ai inference", "scaling laws"]"""


def extract_tags(text: str, *, user_id: str) -> list[str]:
    # Use first 1500 words for tag extraction to keep costs low
    preview = " ".join(text.split()[:1500])
    message = complete(
        model=SONNET,
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"Extract topic tags from this text:\n\n{preview}",
            }
        ],
        system=TAG_SYSTEM_PROMPT,
        user_id=user_id,
        event_type="ingest_tags",
    )
    raw = message.content[0].text.strip()

    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [str(t).lower().strip() for t in tags if t]
    except json.JSONDecodeError:
        pass

    # Fallback: split on commas if JSON parse failed
    return [t.strip().strip('"[]').lower() for t in raw.split(",") if t.strip()]
