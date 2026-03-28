import json
from pathlib import Path
from typing import Any

from config.paths import PROFILE_PATH, PROFILES_DIR

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "role": "",
    "bio": "",
    "location": "",
    "voice_descriptors": [],
    "writing_rules": [],
    "topics_of_expertise": [],
    "target_audience": "",
    "words_to_avoid": [],
    "opinions": [],
    "writing_samples": [],
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
}


def _profile_path(user_id: str = "default") -> Path:
    """Return the correct profile file path for the given user_id.

    For user_id="default", tries the legacy single-file location first
    (backward compat for existing local dev data), then falls back to
    the per-user profiles directory.
    For all other users, uses PROFILES_DIR/profile_{user_id}.json.
    """
    if user_id == "default" and PROFILE_PATH.exists():
        return PROFILE_PATH
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR / f"profile_{user_id}.json"


def load_profile(user_id: str = "default") -> dict[str, Any]:
    path = _profile_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return DEFAULT_PROFILE.copy()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge any missing keys from defaults so profile stays forward-compatible
    changed = False
    for key, value in DEFAULT_PROFILE.items():
        if key not in data:
            data[key] = value
            changed = True
    if changed:
        save_profile(data, user_id)
    return data


def save_profile(profile: dict[str, Any], user_id: str = "default") -> None:
    path = _profile_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def profile_exists(user_id: str) -> bool:
    """Return True if the user has completed onboarding (non-empty name field)."""
    path = _profile_path(user_id)
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("name", "").strip())
    except Exception:
        return False


def profile_to_context_string(profile: dict[str, Any]) -> str:
    lines = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'Unknown')}",
    ]
    if profile.get("bio"):
        lines += ["", f"Bio: {profile['bio']}"]
    if profile.get("target_audience"):
        lines += ["", f"Target audience: {profile['target_audience']}"]
    voice = profile.get("voice_descriptors", [])
    if voice:
        lines += ["", "Voice: " + ", ".join(voice)]
    rules = profile.get("writing_rules", [])
    if rules:
        lines += ["", "Writing rules:", *[f"  - {rule}" for rule in rules]]
    topics = profile.get("topics_of_expertise", [])
    if topics:
        lines += ["", "Topics of expertise: " + ", ".join(topics)]
    avoid = profile.get("words_to_avoid", [])
    if avoid:
        lines += ["", "Words to avoid: " + ", ".join(avoid)]
    opinions = profile.get("opinions", [])
    if opinions:
        lines += ["", "Strong opinions:", *[f"  - {op}" for op in opinions if op]]
    samples = [s for s in profile.get("writing_samples", []) if s]
    if samples:
        lines += ["", "Writing samples (for voice reference):"]
        for i, sample in enumerate(samples, 1):
            lines += [f"  Sample {i}:", f"  {sample[:500]}"]
    return "\n".join(lines)
