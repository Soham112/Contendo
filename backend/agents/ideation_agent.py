import anthropic
import asyncio
import json
import os
import random
from dotenv import load_dotenv

from memory.vector_store import query_similar_hybrid_batch, get_all_tags, get_all_sources
from memory.feedback_store import get_all_topics_posted
from memory.profile_store import load_profile, profile_to_context_string
from memory.usage_store import log_usage_event

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

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

Diversity rules (mandatory):
- Generate ideas that span DIFFERENT topics from the knowledge base — do not cluster ideas around the same theme
- Each idea should draw from a different area of the knowledge base where possible
- Actively look for unexpected connections between different topics in the knowledge base
- If the knowledge base covers 5 topics, your ideas should touch at least 4 of them

Return ONLY a valid JSON array with exactly {count} objects. Each object must have these fields:
- "title": string — specific, catchy, ready to use as-is
- "angle": string — the unique hook or perspective in one sentence
- "format": string — exactly one of: "linkedin post", "medium article", "thread"
- "reasoning": string — one sentence on why this will resonate with their audience

Return nothing outside the JSON array."""


def generate_suggestions(count: int = 8, topic: str | None = None, user_id: str = "default") -> list[dict]:
    count = min(max(count, 1), 15)

    profile = load_profile(user_id=user_id)
    profile_context = profile_to_context_string(profile)

    # Build query list first, then embed everything in a single batched call.
    # This replaces N sequential model forward passes with 1 batched pass.
    query_texts: list[str] = []
    query_top_ks: list[int] = []

    if topic:
        # Topic-focused sampling: drill into the requested topic from multiple angles
        query_texts = [
            topic,
            f"{topic} lessons learned",
            f"{topic} failure or mistake",
        ]
        query_top_ks = [8, 5, 5]
        all_tags = get_all_tags(user_id=user_id)
        if all_tags:
            query_texts.append(random.choice(all_tags))
            query_top_ks.append(4)
    else:
        # Multi-query diversity sampling across the full knowledge base
        broad_queries = ["technology", "career", "learning", "building", "data"]
        query_texts = list(broad_queries)
        query_top_ks = [4] * len(broad_queries)

        # Two random tags for coverage of niche topics
        all_tags = get_all_tags(user_id=user_id)
        if all_tags:
            for tag in random.sample(all_tags, min(2, len(all_tags))):
                query_texts.append(tag)
                query_top_ks.append(5)

        # Oldest source to counteract recency bias
        all_sources = get_all_sources(user_id=user_id)
        if all_sources:
            oldest = sorted(
                [s for s in all_sources if s["ingested_at"]],
                key=lambda s: s["ingested_at"],
            )
            if oldest:
                oldest_title = oldest[0]["source_title"]
                if oldest_title and oldest_title != "Untitled":
                    query_texts.append(oldest_title)
                    query_top_ks.append(5)

    # Hybrid BM25 + vector retrieval with RRF, batched across all queries
    n_results = max(query_top_ks) if query_top_ks else 5
    per_query_results = query_similar_hybrid_batch(query_texts, user_id=user_id, n_results=n_results)
    # Flatten to deduplicated list of text strings, preserving discovery order
    seen_texts: set[str] = set()
    chunks: list[str] = []
    for result_list in per_query_results:
        for chunk_dict in result_list:
            text = chunk_dict.get("text", "")
            if text and text not in seen_texts:
                seen_texts.add(text)
                chunks.append(text)

    posted_topics = get_all_topics_posted(user_id=user_id)

    knowledge_section = (
        "\n\n---\n\n".join(f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks[:30]))
        if chunks
        else "No knowledge base entries yet."
    )

    posted_section = (
        "\n".join(f"- {t}" for t in posted_topics)
        if posted_topics
        else "None yet — all topics are fresh."
    )

    system = SYSTEM_PROMPT.format(count=count)

    topic_instruction = (
        f"\nGenerate ideas specifically focused on: {topic}. All ideas should connect to this theme while drawing from the knowledge base.\n"
        if topic
        else ""
    )

    user_message = f"""Generate {count} content ideas.{topic_instruction}

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

    try:
        asyncio.get_running_loop().create_task(log_usage_event(
            user_id=user_id,
            event_type="ideation",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            metadata={"count": count, "topic": topic or ""},
        ))
    except RuntimeError:
        pass  # No running event loop (e.g. in tests) — skip logging

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
