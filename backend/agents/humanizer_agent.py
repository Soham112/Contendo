import anthropic
import os
from dotenv import load_dotenv

from pipeline.state import PipelineState
from memory.profile_store import profile_to_context_string

load_dotenv()

SYSTEM_PROMPT = """You are a humanizing editor. You take drafts that may still have AI-writing fingerprints and rewrite them to sound like a real human wrote them — specifically, like the person described in the profile below.

User profile:
{profile_context}

AI writing patterns to eliminate:
- Sentences that start with "In today's..." or "It's important to note..."
- Overuse of transition words: "Furthermore", "Moreover", "Additionally", "In conclusion"
- Generic motivational framing: "unlock your potential", "game-changing", "transformative"
- Perfectly balanced sentence lengths — vary them aggressively
- Lists of three that feel formulaic (The three things are: A, B, and C)
- Passive voice where active would be stronger
- Words to avoid: {words_to_avoid}

What to inject instead:
- Sentence variety: mix 4-word punches with longer, winding observations
- Specific details: if the draft says "many companies", name one or say "the last startup I advised"
- Incomplete thoughts that feel real: "Which, honestly, caught me off guard."
- Opinions stated with confidence, not hedged to death
- The writer's actual voice as described in the profile

Current draft:
{current_draft}

Rewrite the draft now. Preserve the structure and all factual content — only change the language and sentence patterns. Output only the rewritten post, no commentary."""


def humanizer_node(state: PipelineState) -> PipelineState:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    profile = state["profile"]
    profile_context = profile_to_context_string(profile)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))
    current_draft = state["current_draft"]

    prompt = SYSTEM_PROMPT.format(
        profile_context=profile_context,
        words_to_avoid=words_to_avoid,
        current_draft=current_draft,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    state["current_draft"] = message.content[0].text.strip()
    state["iterations"] = state.get("iterations", 0) + 1
    return state
