import anthropic
import json
import os
from dotenv import load_dotenv

from memory.vector_store import query_similar
from memory.feedback_store import get_all_topics_posted
from memory.profile_store import load_profile, profile_to_context_string

load_dotenv()

SYSTEM_PROMPT = """You are a content strategist who generates specific, fresh content ideas for a creator.

You will be given:
1. A sample of their knowledge base — what they have been reading, watching, and learning
2. Topics they have already written about — you must not repeat these
3. Their profile — who they are, their expertise, their voice

Your job: generate exactly {count} content ideas they have NOT written about yet, grounded in their actual knowledge.

Rules for good ideas:
- Each title must be specific and punchy — "Why I stopped using feature stores after 3 production projects" not "Best practices for ML"
- Each idea must come from something in their knowledge base — no generic filler ideas
- The angle must be contrarian, personal, or surprising — not "here's how to do X"
- No idea should repeat or closely overlap with their previously posted topics
- Format suggestions must match the idea's natural shape: personal stories → linkedin post, deep dives → medium article, rapid insights → thread

Return ONLY a valid JSON array with exactly {count} objects. Each object must have these fields:
- "title": string — specific, catchy, ready to use as-is
- "angle": string — the unique hook or perspective in one sentence
- "format": string — exactly one of: "linkedin post", "medium article", "thread"
- "reasoning": string — one sentence on why this will resonate with their audience

Return nothing outside the JSON array."""


def generate_suggestions(count: int = 5) -> list[dict]:
    count = min(max(count, 1), 10)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    profile = load_profile()
    profile_context = profile_to_context_string(profile)

    # Broad diverse query to sample knowledge base widely
    diverse_queries = ["technology", "career", "learning", "building", "data"]
    seen_texts: set[str] = set()
    chunks: list[str] = []
    for q in diverse_queries:
        results = query_similar(q, top_k=4)
        for r in results:
            if r["text"] not in seen_texts:
                seen_texts.add(r["text"])
                chunks.append(r["text"])
        if len(chunks) >= 20:
            break

    posted_topics = get_all_topics_posted()

    knowledge_section = (
        "\n\n---\n\n".join(f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks[:20]))
        if chunks
        else "No knowledge base entries yet."
    )

    posted_section = (
        "\n".join(f"- {t}" for t in posted_topics)
        if posted_topics
        else "None yet — all topics are fresh."
    )

    system = SYSTEM_PROMPT.format(count=count)

    user_message = f"""Generate {count} content ideas.

USER PROFILE:
{profile_context}

KNOWLEDGE BASE SAMPLE (use these to ground your ideas):
{knowledge_section}

TOPICS ALREADY WRITTEN ABOUT (do not repeat these):
{posted_section}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        ideas = json.loads(raw)
        if not isinstance(ideas, list):
            raise ValueError("Expected a JSON array")
        # Validate and sanitize each idea
        valid = []
        for idea in ideas:
            if all(k in idea for k in ("title", "angle", "format", "reasoning")):
                valid.append({
                    "title": str(idea["title"]),
                    "angle": str(idea["angle"]),
                    "format": str(idea["format"]).lower(),
                    "reasoning": str(idea["reasoning"]),
                })
        return valid[:count]
    except (json.JSONDecodeError, ValueError):
        return []
