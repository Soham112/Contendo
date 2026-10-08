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
}


def load_profile(user_id: str) -> dict[str, Any]:
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


def save_profile(profile: dict[str, Any], user_id: str) -> None:
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


# Appended once after the user's writing rules, wherever they are shown. A rule
# such as "concrete examples over abstract claims" would otherwise push the model
# to invent an example when the sources have none.
_STYLE_ONLY_RULE = (
    "These rules are about style only. Where one asks for examples, numbers, real moments or "
    "specifics, it means the ones the sources give. Never invent one to satisfy a rule."
)


# Shown above the writing samples wherever they appear. The specifics guard
# enforces it: utils.specifics.profile_facts leaves the samples out of its sources.
WRITING_SAMPLES_RULE = (
    "These are examples of the author's style. Do not reuse any facts, numbers, names or events from them."
)


def _voice_lines(profile: dict[str, Any]) -> list[str]:
    """How the author sounds and who they write for. Nothing here is content."""
    lines = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Role: {profile.get('role', 'Unknown')}",
    ]
    if profile.get("target_audience"):
        lines += ["", f"Target audience: {profile['target_audience']}"]
    voice = profile.get("voice_descriptors", [])
    if voice:
        lines += ["", "Voice: " + ", ".join(voice)]
    rules = profile.get("writing_rules", [])
    if rules:
        lines += ["", "Writing rules:", *[f"  - {rule}" for rule in rules], f"  {_STYLE_ONLY_RULE}"]
    avoid = profile.get("words_to_avoid", [])
    if avoid:
        lines += ["", "Words to avoid: " + ", ".join(avoid)]
    return lines


def _sample_lines(profile: dict[str, Any]) -> list[str]:
    samples = [s for s in profile.get("writing_samples", []) if s]
    if not samples:
        return []
    lines = ["", "Writing samples:", f"  {WRITING_SAMPLES_RULE}"]
    for i, sample in enumerate(samples, 1):
        lines += [f"  Sample {i}:", f"  {sample[:500]}"]
    return lines


def profile_voice_context(profile: dict[str, Any]) -> str:
    """The profile as a voice reference, for prompts that write or judge a post
    (draft, critic, humanizer). Leaves out the bio, topics of expertise and
    opinions: those are content, and a post's content comes from its sources."""
    return "\n".join([*_voice_lines(profile), *_sample_lines(profile)])


def profile_to_context_string(profile: dict[str, Any]) -> str:
    """The whole profile, for prompts that need to know who the author is
    (idea suggestions, selection refine)."""
    lines = _voice_lines(profile)
    if profile.get("bio"):
        lines += ["", f"Bio: {profile['bio']}"]
    topics = profile.get("topics_of_expertise", [])
    if topics:
        lines += ["", "Topics of expertise: " + ", ".join(topics)]
    opinions = profile.get("opinions", [])
    if opinions:
        lines += ["", "Strong opinions:", *[f"  - {op}" for op in opinions if op]]
    return "\n".join([*lines, *_sample_lines(profile)])
