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
Write the draft now. Do not add any preamble or explanation — output only the post content itself.

---
POST STRUCTURE (for story-driven and technical posts):

Strong posts follow this arc — not every section needs to be long, but all six should be present:

1. HOOK — one or two lines maximum. A specific moment, number, or surprising fact. Never a question. Never "I am excited to share."
   Example: "Spent 3 weeks building a RAG pipeline. A college student broke it in 4 minutes."

2. PROBLEM — what actually happened, specifically. Real details, real numbers, real sequence of events. Not "we had challenges" but exactly what broke and how.

3. INSIGHT — the non-obvious realization. What the failure revealed about the system, the assumption, or the architecture. This is the line people share.
   Example: "The architecture itself was the vulnerability."

4. LESSON — where the insight came from. A reference, an experience, a conversation that reframed the problem. Must connect back to the author's actual experience — not a parachuted statistic.
   Example: "Reading how Stripe Radar treats every incoming document as potentially adversarial is what reframed the problem for us."

5. ACTION — what was actually built or changed as a result. Specific. Not "we improved our pipeline" but what specifically was added, removed, or redesigned. Include one friction point — a tradeoff made, latency added, something that broke first.
   Example: "The first thing we added wasn't a better model. It was a pre-ingestion classifier. It added 40ms to every ingest call. Worth it."

6. HONESTY — what is still unsolved, still uncertain, or still a constraint. Never end with a poll question or engagement bait. End with what you still do not know or what you had to accept as a permanent limitation.
   Example: "The pipeline still does not catch everything. Semantic similarity is blind to intent. That is not a bug we fixed — it is a constraint we designed around."

Not every post needs this structure — short opinion posts and personal stories follow their own shape. Apply this arc to technical posts and incident stories.
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
