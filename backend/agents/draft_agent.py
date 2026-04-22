import anthropic
import asyncio
import os
from dotenv import load_dotenv

from pipeline.state import PipelineState
from utils.formatters import get_format_instructions, get_archetype_instructions
from memory.profile_store import profile_to_context_string
from memory.usage_store import log_usage_event
from agents.retrieval_agent import resolve_attribution_frames

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

_ARCHETYPE_HUMAN_NAMES = {
    "incident_report": "Incident Report / Retrospective",
    "contrarian_take": "Contrarian Take",
    "personal_story": "Personal Story",
    "teach_me_something": "Teach Me Something",
    "list_that_isnt": "List That Isn't",
    "prediction_bet": "Prediction / Bet",
    "before_after": "Before & After",
}


_WORD_COUNT_MAP = {
    "linkedin post": {
        "concise":   (100, 180),
        "standard":  (250, 350),
        "long-form": (450, 600),
    },
    "medium article": {
        "concise":   (350, 500),
        "standard":  (700, 900),
        "long-form": (1200, 1800),
    },
    # thread is tweet-count based, not word-count — no enforcement
}


def _get_word_count_rule(format_type: str, length: str) -> str:
    """Return a hard word-count rule string for the given format/length combo.

    Returns an empty string for thread (tweet-based) or unknown formats
    so the prompt is unchanged.
    """
    fmt = format_type.lower().strip()
    lng = length.lower().strip()
    format_lengths = _WORD_COUNT_MAP.get(fmt)
    if format_lengths is None:
        return ""
    min_w, max_w = format_lengths.get(lng, format_lengths["standard"])
    return (
        f"\n---\n"
        f"WORD COUNT RULE — this overrides everything else:\n"
        f"The final post must be {min_w}–{max_w} words.\n"
        f"Count before outputting. If over {max_w}, cut until you are within range.\n"
        f"Never exceed {max_w} words under any circumstance.\n"
        f"---"
    )


def _get_grounding_instruction(confidence: str, chunk_count: int) -> str:
        """Return prompt calibration text based on retrieval confidence.

        High confidence returns an empty string so baseline behavior remains unchanged.
        """
        _ = chunk_count  # kept for future calibration tuning by retrieved chunk count

        if confidence == "high":
                return ""

        if confidence == "medium":
                return """
GROUNDING CALIBRATION:
You have moderate knowledge base coverage on this topic.
Use what is available. Do not invent specifics not present in the chunks.
If you lack a concrete example, write from an observational frame:
"I've seen this pattern" or "this tends to happen when..." rather than
fabricating a named incident or specific timestamp.
Target length: aim for the shorter end of the format's range.
A tighter post with real grounding beats a longer post with filler.
""".strip()

        return """
GROUNDING CALIBRATION:
The knowledge base has limited content on this specific topic.
Write a focused, honest post based only on what is actually in the chunks.
Rules for this post:
- If you only have one real idea from the chunks, write that one idea
    well and stop. 60 to 100 words is a complete post. Do not stretch.
- Write from an analytical or observational perspective, not fabricated
    personal experience
- No invented numbers, timestamps, colleague names, or specific incidents
- Do not tell the reader that your knowledge is limited — just write
    what you know
- Stopping with something real is always better than padding to a
    word count with filler
""".strip()


_ZERO_NOTES_GUARD = """ZERO PERSONAL NOTES RULE (highest priority — overrides all other instructions):
This user has no ingested notes yet. You have ZERO first-person source material.
Do NOT write any personal stories, specific incidents, named colleagues,
specific numbers (AUC scores, percentages, timeframes), or events presented
as things that happened to this person.
Write entirely from an observational or analytical perspective:
- "Most teams underestimate feature engineering" not "At my last job we saw..."
- "The pattern I keep seeing is..." not "When we hit 0.71 AUC..."
- "The instinct is usually to change the model. It's rarely the right call."
A post that shares a sharp observation is better than one that invents a story
the user never lived."""


def infer_archetype(topic: str, context: str, tone: str) -> str:
    """Use Claude Haiku to infer the best archetype. Falls back to incident_report on failure."""
    prompt = f"""You are a content strategist. Given a post topic, tone, and \
optional context, choose the single best archetype for how this post should \
be written.

Topic: {topic}
Tone: {tone}
Context: {context or "none"}

Choose exactly one archetype from this list:
- incident_report: technical failures, production stories, build retrospectives, mistakes made
- contrarian_take: disagreeing with consensus, unpopular opinions, overrated tools or practices
- personal_story: career moments, personal pivots, human experiences, emotional journeys
- teach_me_something: explaining a concept, analogy-driven education, how something works
- list_that_isnt: observations or lessons that work as a subverted list format
- prediction_bet: forward-looking takes, what is coming, industry bets
- before_after: transformation stories, switching tools, decisions that changed everything

Think about what this topic is REALLY about, not just the keywords. \
"My experience with Kubernetes after 2 years" is personal_story not before_after. \
"The thing about LLMs nobody talks about" is contrarian_take not incident_report.

Return ONLY the archetype key, nothing else. No explanation."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        result = message.content[0].text.strip().lower()
        valid = {
            "incident_report", "contrarian_take", "personal_story",
            "teach_me_something", "list_that_isnt", "prediction_bet", "before_after"
        }
        return result if result in valid else "incident_report"
    except Exception:
        return "incident_report"

SYSTEM_PROMPT = """You are a ghostwriter. You write content that sounds exactly like the person described in the user profile below, not like an AI assistant, not generically "professional", but like this specific person.

You have access to their knowledge base: real chunks of content they've read, watched, or written. Use this knowledge to make the draft specific and grounded. Reference real ideas from the chunks; don't write generic claims.

User profile:
{profile_context}

Format and tone instructions:
{format_instructions}
{word_count_rule}

Knowledge base (use what's relevant, ignore the rest):
{retrieved_chunks}

Topic: {topic}
{context_section}
{posted_topics_section}
{grounding_instruction}
Write the draft now. Do not add any preamble or explanation; output only the post content itself.

---
POST STRUCTURE: write this post as a {archetype_name}:
{archetype_instructions}
---

---
SOURCE ATTRIBUTION RULES (mandatory — read chunk labels above before writing):

Chunks are pre-grouped into three frames. Use the frame label to determine
how to write each claim.

PERSONAL frame:
The user directly experienced or built this. Write in first person.
"I ran into this exact problem", "we switched to X because", "I built this and found..."
Never fabricate specific incidents not in the chunk. The chunk is the evidence.

EXPERT OUTSIDER frame:
The user knows adjacent territory deeply but this specific topic is newer to them.
Write with authority and honest curiosity combined.
"Coming from X background, what surprised me about Y is...",
"The mental model shift from X to Y took longer than expected",
"This is what people with X background consistently miss about Y"
Never use passive or student-like framing. They are an expert, just not in this exact thing yet.

LEARNING frame — calibrated by seniority:
Junior (0-3 years): "Been going deep on X lately. Here is what actually matters."
Mid (4-10 years): "X is worth understanding properly. Most explanations miss this."
Senior (10+ years): "X keeps coming up. Here is what I keep seeing people get wrong."
All three are confident. None of them are passive. Never write "I came across an article about X."

CROSS-FRAME RULE:
Never mix frames within a single sentence.
If a paragraph draws on both PERSONAL and LEARNING chunks,
lead with the personal claim and use the learning chunk as supporting evidence.
"I saw this break in production. The pattern is documented — most teams hit it at scale."

FABRICATION RULE (unchanged — still applies):
Never invent personal incidents, timestamps, colleague names, or events
not explicitly present in personal_note chunks or user profile.
---

---
VISUAL PLACEHOLDER RULES (mandatory):
For technical posts about systems, pipelines, architectures, or processes: you MUST include at least one [DIAGRAM: detailed description] placeholder.
The description must be specific enough to draw from.
Good: [DIAGRAM: flowchart showing 5 RAG pipeline stages with failure points marked in red at retrieval layer]
Bad: [DIAGRAM: RAG diagram]

For personal or story posts: include one [IMAGE: description] only if a real photo or screenshot would genuinely strengthen the post.

Never force a diagram into opinion pieces or short punchy posts where the words are the point.
---"""


def _format_retrieval_context(state: PipelineState) -> str:
    """Return the text block to inject as the knowledge base section.

    Priority:
    1. If retrieval_bundle has chunk dicts (with source_type + tags metadata),
       call resolve_attribution_frames() to produce a pre-labeled frame block
       the draft agent reads directly — no interpretive guesswork in the prompt.
    2. Fall back to formatting state["retrieved_chunks"] as a flat numbered list
       (backward compat for pre-migration state or when bundle is absent).
    """
    bundle = state.get("retrieval_bundle") or {}
    bundle_chunks = bundle.get("chunks", [])
    profile = state.get("profile") or {}

    if bundle_chunks:
        return resolve_attribution_frames(bundle_chunks, profile)

    # Flat fallback — preserves pre-hierarchy behavior
    flat_chunks = state.get("retrieved_chunks", [])
    if flat_chunks:
        return "\n\n---\n\n".join(
            f"[Chunk {i + 1}]\n{chunk}" for i, chunk in enumerate(flat_chunks)
        )
    return "No relevant knowledge base entries found. Draw on general expertise."


def draft_node(state: PipelineState) -> PipelineState:
    # Infer archetype from topic/context/tone — no Claude call, deterministic
    archetype = infer_archetype(
        topic=state.get("topic", ""),
        context=state.get("context", ""),
        tone=state.get("tone", ""),
    )
    state["archetype"] = archetype
    archetype_name = _ARCHETYPE_HUMAN_NAMES.get(archetype, archetype)
    archetype_instructions = get_archetype_instructions(archetype)

    profile = state["profile"]
    profile_context = profile_to_context_string(profile)
    format_instructions = get_format_instructions(
        state["format"],
        state.get("length", "standard"),
        state["tone"],
    )
    word_count_rule = _get_word_count_rule(state["format"], state.get("length", "standard"))

    chunks_text = _format_retrieval_context(state)

    context = state.get("context", "").strip()
    context_section = f"Additional context: {context}" if context else ""

    posted_topics = state.get("posted_topics", [])
    if posted_topics:
        listed = "\n".join(f"- {t}" for t in posted_topics)
        posted_topics_section = (
            f"Topics you have already written about — do not repeat these angles, find a fresh perspective:\n{listed}\n"
        )
    else:
        posted_topics_section = ""

    grounding_instruction = _get_grounding_instruction(
        state.get("retrieval_confidence", "medium"),
        state.get("retrieved_chunk_count", 0),
    )

    if "No relevant knowledge base entries found" in chunks_text:
        grounding_instruction = (
            _ZERO_NOTES_GUARD + ("\n\n" + grounding_instruction if grounding_instruction else "")
        )

    prompt = SYSTEM_PROMPT.format(
        profile_context=profile_context,
        format_instructions=format_instructions,
        word_count_rule=word_count_rule,
        retrieved_chunks=chunks_text,
        topic=state["topic"],
        context_section=context_section,
        posted_topics_section=posted_topics_section,
        grounding_instruction=grounding_instruction,
        archetype_name=archetype_name,
        archetype_instructions=archetype_instructions,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    state["current_draft"] = message.content[0].text.strip()

    try:
        asyncio.get_running_loop().create_task(log_usage_event(
            user_id=state.get("user_id", "default"),
            event_type="generate",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            metadata={
                "topic": state.get("topic", ""),
                "format": state.get("format", ""),
                "archetype": state.get("archetype", ""),
            },
        ))
    except RuntimeError:
        pass

    return state
