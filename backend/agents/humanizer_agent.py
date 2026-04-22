import anthropic
import asyncio
import os
import re
from dotenv import load_dotenv

from pipeline.state import PipelineState
from memory.profile_store import load_profile, profile_to_context_string
from memory.usage_store import log_usage_event

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

SYSTEM_PROMPT = """You are a humanizing editor. You take drafts that may still have AI-writing fingerprints and rewrite them to sound like a real human wrote them, specifically like the person described in the profile below.

User profile:
{profile_context}

{critic_section}AI writing patterns to eliminate:
- Sentences that start with "In today's..." or "It's important to note..."
- Overuse of transition words: "Furthermore", "Moreover", "Additionally", "In conclusion"
- Generic motivational framing: "unlock your potential", "game-changing", "transformative"
- Perfectly balanced sentence lengths; vary them aggressively
- Lists of three that feel formulaic (The three things are: A, B, and C)
- Passive voice where active would be stronger
- Em dashes used as clause connectors or parenthetical separators (e.g. 'the data was messy, noisy and sparse' or 'one feature, which had low fill rate, was dropped'). Replace with a period, a comma, or rewrite the sentence entirely. Em dashes are one of the strongest signals of AI-generated text and must never appear in the output.
- Hyphenated compound modifiers used decoratively (e.g. 'data-driven', 'production-ready', 'well-known', 'high-value' when plain language works just as well). Write 'drives decisions with data' not 'data-driven'. Only use hyphens when they are grammatically required and cannot be avoided.
- Words to avoid: {words_to_avoid}

Never use the em dash character (—) anywhere in the output. If you are about to write an em dash, stop and use a period or comma instead.

What to inject instead:
- Sentence variety: mix 4-word punches with longer, winding observations
- Specific details: if the draft says "many companies", name one or say "the last startup I advised"
- Incomplete thoughts that feel real: "Which, honestly, caught me off guard."
- Opinions stated with confidence, not hedged to death
- The writer's actual voice as described in the profile

Current draft:
{current_draft}

{rewrite_instruction}"""


def _format_critic_brief(critic_brief: dict) -> tuple[str, str]:
    """Format critic_brief dict into (critic_section, rewrite_instruction) for SYSTEM_PROMPT.

    Returns empty critic_section and a preserve-structure instruction when the brief
    is empty (draft mode / error) or all areas are "strong".
    Returns a populated critic_section and a fix-first instruction when any area
    has verdict "needs_work".
    """
    _preserve = (
        "Rewrite the draft now. Preserve the structure and all factual content — "
        "only change the language and sentence patterns. Output only the rewritten post, no commentary."
    )
    _fix_first = (
        "Rewrite the draft now. Fix the flagged issues above first — in this order: "
        "hook, substance, structure, voice. You may rewrite the hook entirely, restructure sections, "
        "and add specific grounding from the knowledge base. Then do a full language humanization pass. "
        "Output only the rewritten post, no commentary."
    )

    if not critic_brief:
        return "", _preserve

    _areas = ["hook", "substance", "structure", "voice"]
    flagged = []
    for area in _areas:
        entry = critic_brief.get(area, {})
        if isinstance(entry, dict) and entry.get("verdict") == "needs_work" and entry.get("fix"):
            flagged.append(f"- {area.upper()}: {entry['fix']}")

    if not flagged:
        return "", _preserve

    critic_section = (
        "CRITIC BRIEF — fix these issues before humanizing, in this order:\n"
        + "\n".join(flagged)
        + "\n\n"
    )
    return critic_section, _fix_first


REFINE_PROMPT = """You are a sharp editor rewriting a post draft based on specific feedback. Your job is to make meaningful improvements, not cosmetic tweaks.

User profile: write in this person's voice:
{profile_context}

Words this person never uses:
{words_to_avoid}

Never use the em dash character (—) anywhere in the output. If you are about to write an em dash, stop and use a period or comma instead.

AI writing patterns to eliminate from the output:
- Em dashes used as clause connectors or parenthetical separators (e.g. 'the data was messy, noisy and sparse' or 'one feature, which had low fill rate, was dropped'). Replace with a period, a comma, or rewrite the sentence entirely. Em dashes are one of the strongest signals of AI-generated text and must never appear in the output.
- Hyphenated compound modifiers used decoratively (e.g. 'data-driven', 'production-ready', 'well-known', 'high-value' when plain language works just as well). Write 'drives decisions with data' not 'data-driven'. Only use hyphens when they are grammatically required and cannot be avoided.

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
  Add the missing substance. If the feedback asks for what actually happened: write something that sounds like it actually happened, grounded in the user's profile and experience. If you don't have the specific detail, write something honest: "I don't have the exact number, but the pattern was clear."

What to always preserve:
  - [DIAGRAM:] and [IMAGE:] placeholders are MANDATORY. They must appear in the output exactly as written. If you restructure paragraphs, place the placeholder where it best fits the new structure, but never omit it. Missing a placeholder is a critical error.
  - Specific real numbers and named facts that are clearly sourced
  - The overall topic and argument

What you are allowed to change:
  - Paragraph order
  - Sentence structure throughout
  - The opening and closing
  - Any section the feedback identifies as weak
  - Length: shorter is often better

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


async def refine_selection(
    selected_text: str,
    instruction: str,
    full_post: str,
    user_id: str = "default",
) -> str:
    """Rewrite only a selected fragment using full-post context for voice matching."""
    profile = load_profile(user_id)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))

    prompt = f"""You are editing a specific section of a social media post.

User profile — match this person's voice exactly:
{profile_to_context_string(profile)}

Words this person never uses: {words_to_avoid}

Never use the em dash character (—) anywhere in the output.

Full post for context (do NOT rewrite this — for voice reference only):
{full_post}

Selected section to rewrite:
{selected_text}

Instruction: {instruction}

Rules:
- Rewrite ONLY the selected section according to the instruction
- Match the voice, tone, and style of the surrounding post exactly
- Output ONLY the rewritten text — no explanation, no preamble, no quotes
- Do not add line breaks unless the original had them
- Keep roughly the same length unless the instruction says otherwise
- No em dashes anywhere in the output"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def humanizer_node(state: PipelineState) -> PipelineState:
    if state.get("quality") == "draft":
        return state  # pass raw draft through unchanged

    profile = state["profile"]
    profile_context = profile_to_context_string(profile)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))
    current_draft = state["current_draft"]

    critic_section, rewrite_instruction = _format_critic_brief(state.get("critic_brief", {}))

    prompt = SYSTEM_PROMPT.format(
        profile_context=profile_context,
        words_to_avoid=words_to_avoid,
        current_draft=current_draft,
        critic_section=critic_section,
        rewrite_instruction=rewrite_instruction,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    state["current_draft"] = message.content[0].text.strip()
    state["iterations"] = state.get("iterations", 0) + 1

    try:
        asyncio.get_running_loop().create_task(log_usage_event(
            user_id=state.get("user_id", "default"),
            event_type="humanize",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        ))
    except RuntimeError:
        pass

    return state
