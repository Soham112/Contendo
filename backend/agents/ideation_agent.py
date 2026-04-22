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


def _source_label(source_type: str) -> str:
    if source_type == "personal_note":
        return "[from: personal experience]"
    if source_type in ("article", "saved_content"):
        return "[from: article/saved content]"
    if source_type == "youtube":
        return "[from: video/talk]"
    if source_type == "note":
        return "[from: note]"
    return "[from: general knowledge]"


client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

SYSTEM_PROMPT = """You are a content strategist who generates specific, fresh content ideas for a creator.

You will be given:
1. A sample of their knowledge base — labelled by source type so you know where each piece of knowledge came from
2. Topics they have already written about — do not repeat these angles
3. Their profile — who they are, their expertise, their voice

Your job: generate exactly {count} content ideas grounded in their actual knowledge.

The same topic can appear more than once if the angle and frame are genuinely different.
What must never repeat is the writing posture — the combination of frame + angle.

WRITING FRAME RULES — mandatory, this overrides all other diversity rules:

Each idea must be assigned one of these five frames. If count >= 5, all five frames must appear at least once. If count < 5, use the most distinct frames possible — never use the same frame more than twice.

FRAME: personal_experience
For chunks labelled [from: personal experience].
The idea comes from something the creator lived, decided, or got wrong.
Angle shape: "the moment X happened / the decision I regret / what broke before it worked"
Title must not say "I learned" or "lesson" — name the event or the outcome directly.

FRAME: absorbed_insight
For chunks labelled [from: article/saved content] or [from: video/talk] or [from: note].
The creator read or watched something, and it changed how they think. The idea is their perspective now — the source is never mentioned in the title or angle.
Angle shape: "the idea that reframes how I think about X / what most people miss about Y / the thing Z gets wrong"
Never write "I read a paper" or "I watched a video" — the knowledge belongs to them now.

FRAME: observed_pattern
For any chunk, any source type.
Something the creator keeps noticing in their industry, in other people's work, in how teams or systems behave — without it being their own story.
Angle shape: "why most teams do X wrong / the quiet failure mode nobody names / what separates X from Y in practice"

FRAME: contrarian_take
For any chunk, any source type.
A specific belief that is widely held in their field that they think is wrong or dangerously incomplete.
Angle shape: "everyone says X — here is why that breaks / the advice that sounds right but costs you in production"
Must be specific and defensible — not vague disagreement.

FRAME: forward_prediction
For any chunk, any source type.
Where something in their field is heading, grounded in what is already visible in their knowledge base — not speculation.
Angle shape: "the shift already happening that nobody is writing about / what X looks like in two years if Y keeps going"

TITLE RULES:
- Specific and punchy — name the thing, not the category
- No "best practices", no "lessons learned", no "a guide to"
- No "I read / I watched / I came across" in absorbed_insight titles
- The title should be publishable as-is

FORMAT MATCHING:
- personal_experience → linkedin post
- absorbed_insight → linkedin post or thread depending on depth
- observed_pattern → thread or medium article
- contrarian_take → linkedin post or thread
- forward_prediction → medium article or thread

Return ONLY a valid JSON array with exactly {count} objects. Each object:
- "title": string
- "angle": string — the unique hook in one sentence
- "format": string — exactly one of: "linkedin post", "medium article", "thread"
- "frame": string — exactly one of: "personal_experience", "absorbed_insight", "observed_pattern", "contrarian_take", "forward_prediction"
- "reasoning": string — one sentence on why this will resonate

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
    # Flatten to deduplicated list, preserving discovery order
    seen_texts: set[str] = set()
    chunks: list[dict] = []
    for result_list in per_query_results:
        for chunk_dict in result_list:
            text = chunk_dict.get("text", "")
            if text and text not in seen_texts:
                seen_texts.add(text)
                chunks.append({
                    "text": text,
                    "source_type": chunk_dict.get("source_type", ""),
                })

    posted_topics = get_all_topics_posted(user_id=user_id)

    knowledge_section = (
        "\n\n---\n\n".join(
            f"[Chunk {i+1}] {_source_label(c['source_type'])}\n{c['text']}"
            for i, c in enumerate(chunks[:30])
        )
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
            if all(k in idea for k in ("title", "angle", "format", "frame", "reasoning")):
                valid.append({
                    "title": str(idea["title"]),
                    "angle": str(idea["angle"]),
                    "format": str(idea["format"]).lower(),
                    "frame": str(idea["frame"]).lower(),
                    "reasoning": str(idea["reasoning"]),
                })
        return valid[:count]
    except (json.JSONDecodeError, ValueError):
        return []
