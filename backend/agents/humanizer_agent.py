import anthropic
import os
import re
from dotenv import load_dotenv

from pipeline.state import PipelineState
from memory.profile_store import load_profile, profile_to_context_string

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

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


REFINE_PROMPT = """You are a sharp editor rewriting a post draft based on specific feedback. Your job is to make meaningful improvements — not cosmetic tweaks.

User profile — write in this person's voice:
{profile_context}

Words this person never uses:
{words_to_avoid}

Current draft:
{current_draft}

Feedback to act on:
{refinement_instruction}

How to approach this:

For STRUCTURAL feedback (move this section, cut this paragraph, the ending is weak):
  Make the structural change. Move paragraphs. Cut what is not working. Rewrite the ending if the feedback says it is weak. Do not preserve structure at the cost of quality.

For VOICE feedback (too clean, too generic, reads like LLM output, lacks specificity):
  Rewrite the affected sentences from scratch in the user's voice. Use the profile above as your guide. One specific detail beats three general claims every time.

For CONTENT feedback (reference feels parachuted, missing what actually happened, no friction):
  Add the missing substance. If the feedback asks for what actually happened — write something that sounds like it actually happened, grounded in the user's profile and experience. If you don't have the specific detail, write something honest: "I don't have the exact number, but the pattern was clear."

What to always preserve:
  - [DIAGRAM:] and [IMAGE:] placeholders are MANDATORY. They must appear in the output exactly as written. If you restructure paragraphs, place the placeholder where it best fits the new structure — but never omit it. Missing a placeholder is a critical error.
  - Specific real numbers and named facts that are clearly sourced
  - The overall topic and argument

What you are allowed to change:
  - Paragraph order
  - Sentence structure throughout
  - The opening and closing
  - Any section the feedback identifies as weak
  - Length — shorter is often better

Output only the refined post. No commentary. No "Here is the refined version:" preamble."""


def refine_draft(
    current_draft: str,
    refinement_instruction: str,
    profile: dict = None,
) -> str:
    if profile is None:
        profile = load_profile()

    profile_context = profile_to_context_string(profile)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))

    prompt = REFINE_PROMPT.format(
        profile_context=profile_context,
        words_to_avoid=words_to_avoid,
        current_draft=current_draft,
        refinement_instruction=refinement_instruction,
    )
    placeholders = re.findall(r'\[(?:DIAGRAM|IMAGE):.*?\]', current_draft, re.DOTALL)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    refined_text = message.content[0].text.strip()

    for placeholder in placeholders:
        if placeholder not in refined_text:
            paragraphs = refined_text.strip().split('\n\n')
            insert_at = max(0, len(paragraphs) - 2)
            paragraphs.insert(insert_at, placeholder)
            refined_text = '\n\n'.join(paragraphs)

    return refined_text


def humanizer_node(state: PipelineState) -> PipelineState:
    if state.get("quality") == "draft":
        return state  # pass raw draft through unchanged

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
