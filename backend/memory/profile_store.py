import logging
from typing import Any

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

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
    "extension_banner_dismissed": False,
}


def load_profile(user_id: str = "default") -> dict[str, Any]:
    logger.info(f"load_profile: fetching from Supabase for user_id={user_id}")
    result = (
        supabase.table("profiles")
        .select("data")
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        logger.info(f"load_profile: no row found for user_id={user_id}, returning DEFAULT_PROFILE")
        return DEFAULT_PROFILE.copy()
    data: dict[str, Any] = result.data[0]["data"]
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
    logger.info(f"save_profile: upserting to Supabase for user_id={user_id}")
    supabase.table("profiles").upsert({"id": user_id, "data": profile}).execute()
    logger.info(f"save_profile: successfully saved profile for user_id={user_id}")


def profile_exists(user_id: str) -> bool:
    """Return True if a profile row exists for this user in Supabase."""
    logger.info(f"profile_exists: checking Supabase for user_id={user_id}")
    result = (
        supabase.table("profiles")
        .select("id")
        .eq("id", user_id)
        .execute()
    )
    exists = bool(result.data)
    logger.info(f"profile_exists: {exists} for user_id={user_id}")
    return exists


def save_writing_sample(user_id: str, sample: str, max_samples: int = 10) -> None:
    """Append a new writing sample to the user's profile (deduplicated, capped at max_samples)."""
    sample = sample.strip()
    if not sample:
        return
    profile = load_profile(user_id)
    samples: list[str] = [s for s in profile.get("writing_samples", []) if s]
    normalized = [s.lower() for s in samples]
    if sample.lower() not in normalized:
        samples.append(sample)
    if len(samples) > max_samples:
        samples = samples[-max_samples:]
    profile["writing_samples"] = samples
    save_profile(profile, user_id)
    logger.info(f"save_writing_sample: added sample for user_id={user_id}, total={len(samples)}")


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
