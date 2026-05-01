import anthropic
import asyncio
import json
import os
import random
from dotenv import load_dotenv

from memory.vector_store import query_similar_hybrid_batch, get_all_tags, get_all_sources, get_total_chunks
from memory.feedback_store import get_all_topics_posted
from memory.profile_store import load_profile, profile_to_context_string
from memory.experience_store import get_experience_nodes, experience_nodes_exist, experience_nodes_to_context_string
from memory.usage_store import log_usage_event

load_dotenv()

# KB is considered sparse below this chunk count
SPARSE_KB_THRESHOLD = 10


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

GROUNDING RULE — this is the most important rule and overrides everything else:
Every idea you generate must be directly traceable to a specific chunk or experience entry provided above.
Do not invent topics, angles, frameworks, or opinions that have no basis in the provided knowledge.
If a chunk says X, you can build an angle from X. You cannot invent Y and pretend it came from the knowledge base.
When in doubt, be more conservative — a specific idea grounded in one real chunk is worth more than a clever idea you invented.

The same topic can appear more than once if the angle and frame are genuinely different.
What must never repeat is the writing posture — the combination of frame + angle.

WRITING FRAME RULES — mandatory, this overrides all other diversity rules:

Each idea must be assigned one of these five frames. If count >= 5, all five frames must appear at least once. If count < 5, use the most distinct frames possible — never use the same frame more than twice.

FRAME: personal_experience
For chunks labelled [from: personal experience] or experience entries from their work/project history.
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

RESUME_SYSTEM_PROMPT = """You are a content strategist who generates specific, fresh content ideas for a creator who is just getting started.

You will be given:
1. Their structured work and project history — extracted from their resume
2. Their profile — who they are, their expertise, their voice
3. Topics they have already written about — do not repeat these angles

Their knowledge base is still being built. Generate ideas grounded strictly in their actual career experience and projects — not in general wisdom or things they might know.

GROUNDING RULE — this is the most important rule:
Every idea must trace directly to a specific job, project, or experience listed in their history.
Do not invent frameworks, opinions, or angles that aren't visible in their actual career.
A specific idea about one real project beats a broad generic idea about their industry.

The same company or project can appear more than once if the angle and frame are genuinely different.

WRITING FRAME RULES — mandatory:

Each idea must be assigned one of these five frames. If count >= 5, all five frames must appear at least once.

FRAME: personal_experience
Something they actually did, decided, or shipped at a specific job or project.
Angle shape: "the moment X happened / what we got wrong at [company] / how I built [thing]"

FRAME: absorbed_insight
Something their career taught them that changed how they think — framed as their perspective, not a job description.
Angle shape: "working at [domain] taught me that X / the thing nobody tells you about [role]"

FRAME: observed_pattern
A pattern they kept seeing across their roles or projects — not their personal story, but something they watched repeatedly.
Angle shape: "every [role] I've seen does X wrong / the one thing that separated good [outcome] from bad [outcome]"

FRAME: contrarian_take
A widely-held belief in their field they disagree with, grounded in something specific they actually experienced.
Must be traceable to a real experience — not a generic industry complaint.

FRAME: forward_prediction
Where something in their field is heading, grounded in concrete trends visible in their career history — not speculation.

TITLE RULES:
- Specific — name the project, company type, or decision, not the category
- No "lessons learned", "best practices", "a guide to"
- Publishable as-is

Return ONLY a valid JSON array with exactly {count} objects. Each object:
- "title": string
- "angle": string — the unique hook in one sentence
- "format": string — exactly one of: "linkedin post", "medium article", "thread"
- "frame": string — exactly one of: "personal_experience", "absorbed_insight", "observed_pattern", "contrarian_take", "forward_prediction"
- "reasoning": string — one sentence on why this will resonate

Return nothing outside the JSON array."""



def generate_suggestions(count: int = 8, topic: str | None = None, user_id: str = "default") -> list[dict] | dict:
    count = min(max(count, 1), 15)

    profile = load_profile(user_id=user_id)
    profile_context = profile_to_context_string(profile)
    posted_topics = get_all_topics_posted(user_id=user_id)

    posted_section = (
        "\n".join(f"- {t}" for t in posted_topics)
        if posted_topics
        else "None yet — all topics are fresh."
    )

    # ── Check KB density ──────────────────────────────────────────────────────
    chunk_count = get_total_chunks(user_id=user_id)
    kb_is_sparse = chunk_count < SPARSE_KB_THRESHOLD

    # ── Sparse KB path ────────────────────────────────────────────────────────
    if kb_is_sparse:
        if experience_nodes_exist(user_id=user_id):
            # Use resume/experience nodes as the idea seed
            nodes = get_experience_nodes(user_id=user_id)
            experience_context = experience_nodes_to_context_string(nodes)
            return _generate_from_resume(
                count=count,
                topic=topic,
                profile_context=profile_context,
                experience_context=experience_context,
                posted_section=posted_section,
                user_id=user_id,
            )
        else:
            # No KB and no resume — signal the frontend to prompt the user
            return {"sparse": True, "suggestions": []}

    # ── Rich KB path — retrieve and generate ─────────────────────────────────
    all_tags = get_all_tags(user_id=user_id)

    # Build profile-aware sampling queries
    query_texts: list[str] = []
    query_top_ks: list[int] = []

    if topic:
        query_texts = [
            topic,
            f"{topic} lessons learned",
            f"{topic} failure or mistake",
        ]
        query_top_ks = [8, 5, 5]
        if all_tags:
            query_texts.append(random.choice(all_tags))
            query_top_ks.append(4)
    else:
        user_topics: list[str] = [t for t in profile.get("topics_of_expertise", []) if t.strip()]

        if user_topics:
            sampled_topics = random.sample(user_topics, min(5, len(user_topics)))
            for t in sampled_topics:
                query_texts.append(t)
                query_top_ks.append(4)
        else:
            role = profile.get("role", "").strip()
            bio = profile.get("bio", "").strip()
            if role:
                query_texts.append(role)
                query_top_ks.append(5)
            if bio:
                first_sentence = bio.split(".")[0].strip()
                if first_sentence:
                    query_texts.append(first_sentence)
                    query_top_ks.append(5)
            if not query_texts:
                query_texts = ["career", "building", "learning"]
                query_top_ks = [4, 4, 4]

        # Up to 2 random tags for niche coverage
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

    n_results = max(query_top_ks) if query_top_ks else 5
    per_query_results = query_similar_hybrid_batch(query_texts, user_id=user_id, n_results=n_results)

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

    knowledge_section = (
        "\n\n---\n\n".join(
            f"[Chunk {i+1}] {_source_label(c['source_type'])}\n{c['text']}"
            for i, c in enumerate(chunks[:30])
        )
        if chunks
        else "No knowledge base entries yet."
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

KNOWLEDGE BASE SAMPLE (use these to ground your ideas — every idea must trace to one of these chunks):
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
            metadata={"count": count, "topic": topic or "", "kb_chunks": len(chunks)},
        ))
    except RuntimeError:
        pass

    return _parse_ideas(message.content[0].text.strip(), count)


def _generate_from_resume(
    count: int,
    topic: str | None,
    profile_context: str,
    experience_context: str,
    posted_section: str,
    user_id: str,
) -> list[dict]:
    """Generate ideas seeded from experience nodes when the KB is sparse."""
    system = RESUME_SYSTEM_PROMPT.format(count=count) if "{count}" in RESUME_SYSTEM_PROMPT else RESUME_SYSTEM_PROMPT

    topic_instruction = (
        f"\nFocus ideas around: {topic}. Draw from experience entries that relate to this theme.\n"
        if topic
        else ""
    )

    user_message = f"""Generate {count} content ideas.{topic_instruction}

USER PROFILE:
{profile_context}

WORK & PROJECT HISTORY (ground every idea in one of these entries):
{experience_context}

TOPICS ALREADY WRITTEN ABOUT (do not repeat these):
{posted_section}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=RESUME_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    try:
        asyncio.get_running_loop().create_task(log_usage_event(
            user_id=user_id,
            event_type="ideation",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            metadata={"count": count, "topic": topic or "", "source": "resume_fallback"},
        ))
    except RuntimeError:
        pass

    return _parse_ideas(message.content[0].text.strip(), count)


def _parse_ideas(raw: str, count: int) -> list[dict]:
    """Parse and validate the JSON array returned by Claude."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        ideas = json.loads(raw)
        if not isinstance(ideas, list):
            raise ValueError("Expected a JSON array")
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
