import anthropic
import os
from dotenv import load_dotenv

from memory.vector_store import upsert_chunks
from utils.chunker import chunk_text

load_dotenv()

SYSTEM_PROMPT = """You are a tag extraction assistant. Given a passage of text, extract 3–8 short, lowercase topic tags that best describe what this content is about.

Rules:
- Tags must be 1–3 words each
- Use specific, meaningful terms (e.g. "machine learning", "product strategy", "ux research")
- Avoid generic tags like "article", "text", "content", "post"
- Return ONLY a JSON array of strings, nothing else

Example output: ["machine learning", "transformer models", "ai inference", "scaling laws"]"""


def _extract_tags(text: str) -> list[str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # Use first 1500 words for tag extraction to keep costs low
    preview = " ".join(text.split()[:1500])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"Extract topic tags from this text:\n\n{preview}",
            }
        ],
        system=SYSTEM_PROMPT,
    )
    raw = message.content[0].text.strip()

    import json
    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [str(t).lower().strip() for t in tags if t]
    except json.JSONDecodeError:
        pass

    # Fallback: split on commas if JSON parse failed
    return [t.strip().strip('"[]').lower() for t in raw.split(",") if t.strip()]


def ingest_content(content: str, source_type: str) -> dict:
    chunks = chunk_text(content)
    if not chunks:
        return {"chunks_stored": 0, "tags": []}

    tags = _extract_tags(content)
    stored = upsert_chunks(chunks, source_type=source_type, tags=tags)

    return {"chunks_stored": stored, "tags": tags}
