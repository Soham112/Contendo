import anthropic
import os
from dotenv import load_dotenv

from pipeline.state import PipelineState
from utils.formatters import get_format_instructions, get_archetype_instructions
from memory.profile_store import profile_to_context_string

load_dotenv()


_ARCHETYPE_HUMAN_NAMES = {
    "incident_report": "Incident Report / Retrospective",
    "contrarian_take": "Contrarian Take",
    "personal_story": "Personal Story",
    "teach_me_something": "Teach Me Something",
    "list_that_isnt": "List That Isn't",
    "prediction_bet": "Prediction / Bet",
    "before_after": "Before & After",
}


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
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
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

SYSTEM_PROMPT = """You are a ghostwriter. You write content that sounds exactly like the person described in the user profile below — not like an AI assistant, not generically "professional", but like this specific person.

You have access to their knowledge base: real chunks of content they've read, watched, or written. Use this knowledge to make the draft specific and grounded. Reference real ideas from the chunks — don't write generic claims.

User profile:
{profile_context}

Format and tone instructions:
{format_instructions}

Knowledge base (use what's relevant, ignore the rest):
{retrieved_chunks}

Topic: {topic}
{context_section}
{posted_topics_section}
Write the draft now. Do not add any preamble or explanation — output only the post content itself.

---
POST STRUCTURE — write this post as a {archetype_name}:
{archetype_instructions}
---

---
VISUAL PLACEHOLDER RULES (mandatory):
For technical posts about systems, pipelines, architectures, or processes — you MUST include at least one [DIAGRAM: detailed description] placeholder.
The description must be specific enough to draw from.
Good: [DIAGRAM: flowchart showing 5 RAG pipeline stages with failure points marked in red at retrieval layer]
Bad: [DIAGRAM: RAG diagram]

For personal or story posts — include one [IMAGE: description] only if a real photo or screenshot would genuinely strengthen the post.

Never force a diagram into opinion pieces or short punchy posts where the words are the point.
---"""


def draft_node(state: PipelineState) -> PipelineState:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
    format_instructions = get_format_instructions(state["format"], state["tone"])

    chunks = state.get("retrieved_chunks", [])
    if chunks:
        chunks_text = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)
        )
    else:
        chunks_text = "No relevant knowledge base entries found. Draw on general expertise."

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

    prompt = SYSTEM_PROMPT.format(
        profile_context=profile_context,
        format_instructions=format_instructions,
        retrieved_chunks=chunks_text,
        topic=state["topic"],
        context_section=context_section,
        posted_topics_section=posted_topics_section,
        archetype_name=archetype_name,
        archetype_instructions=archetype_instructions,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    state["current_draft"] = message.content[0].text.strip()
    return state
