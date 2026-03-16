import anthropic
import os
from dotenv import load_dotenv

from pipeline.state import PipelineState
from utils.formatters import get_format_instructions
from memory.profile_store import profile_to_context_string

load_dotenv()

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
Visual placeholders:
Include a [DIAGRAM: description] placeholder only when the post contains a technical concept, process, or comparison that would be genuinely clearer as a visual — for example a pipeline, architecture, workflow, or step-by-step process.

Do not force a diagram into opinion pieces, personal stories, or short punchy posts where the words are the point. If the post does not need a diagram, do not include one.

When a diagram does belong, make the description specific enough to draw from — not just 'RAG diagram' but 'flowchart showing the 5 stages of RAG with failure points marked at the retrieval stage'.

For personal or story posts where a real photo would add credibility — a competition, a team moment, a screenshot of real work — include one [IMAGE: description] placeholder suggesting exactly what photo or screenshot would work.

Write the draft now. Do not add any preamble or explanation — output only the post content itself."""


def draft_node(state: PipelineState) -> PipelineState:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    state["current_draft"] = message.content[0].text.strip()
    return state
