import json
from pathlib import Path
from typing import Any

from config.paths import PROFILE_PATH

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "Soham",
    "role": "Builder and founder",
    "voice_descriptors": [
        "direct",
        "opinionated",
        "first-person",
        "conversational",
        "no fluff",
    ],
    "writing_rules": [
        "Never start sentences with 'I' back-to-back.",
        "Use short paragraphs — max 3 sentences.",
        "Prefer concrete examples over abstract claims.",
        "No corporate jargon or buzzwords.",
        "Vary sentence length: mix short punchy lines with longer ones.",
        "Avoid passive voice.",
        "Never use filler phrases like 'In conclusion' or 'It is worth noting'.",
    ],
    "topics_of_expertise": [
        "AI and LLMs",
        "product building",
        "startups",
        "developer tools",
    ],
    "linkedin_style_notes": (
        "Hook in the first line — no slow builds. "
        "End with a takeaway or question, not a CTA. "
        "Use line breaks aggressively — one idea per line."
    ),
    "medium_style_notes": (
        "Start in the middle of the story. "
        "Use subheadings to break structure. "
        "Technical depth is welcome — don't dumb it down."
    ),
    "thread_style_notes": (
        "Each tweet stands alone but pulls into the next. "
        "Number tweets. "
        "Last tweet is the payoff."
    ),
    "words_to_avoid": [
        "leverage",
        "synergy",
        "delve",
        "unlock",
        "game-changer",
        "revolutionary",
        "transformative",
        "it's important to note",
        "in today's world",
        "crucial",
    ],
}


def load_profile() -> dict[str, Any]:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        save_profile(DEFAULT_PROFILE)
        return DEFAULT_PROFILE.copy()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge any missing keys from defaults so profile stays forward-compatible
    changed = False
    for key, value in DEFAULT_PROFILE.items():
        if key not in data:
            data[key] = value
            changed = True
    if changed:
        save_profile(data)
    return data


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def profile_to_context_string(profile: dict[str, Any]) -> str:
    lines = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'Unknown')}",
        "",
        "Voice: " + ", ".join(profile.get("voice_descriptors", [])),
        "",
        "Writing rules:",
        *[f"  - {rule}" for rule in profile.get("writing_rules", [])],
        "",
        "Topics of expertise: " + ", ".join(profile.get("topics_of_expertise", [])),
        "",
        "Words to avoid: " + ", ".join(profile.get("words_to_avoid", [])),
    ]
    return "\n".join(lines)
