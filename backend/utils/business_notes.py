"""The notes a business user's answers are saved to memory as.

Both are plain text built from what the user typed, then stored through the
normal ingestion path (agents.ingestion_agent.ingest_content). The profile note
is retained for Library and rollback; with the business block enabled, account
facts reach generation directly and its stored note is excluded from retrieval.

Where the answers came from does not matter here: a later website import or
voice input fills the same business profile fields and reuses profile_note.
"""

from typing import Any

from config import features

from config.niches import OTHER_NICHE, SEGMENT_BUSINESS, TONES_BY_KEY, Niche, Pillar, get_niche

# The one title the profile note is stored under, so saving the profile again
# replaces the note instead of adding a second one.
PROFILE_NOTE_TITLE = "Business profile"
# Bump when profile_note changes what it writes (recorded per source).
PROFILE_NOTE_EXTRACTOR = ("business_notes.profile_note", "1")

# Label and business_profile key, in the order the note lists them.
_PROFILE_LINES = (
    ("Business name", "business_name"),
    ("Area served", "service_area"),
    ("Website", "website"),
    ("What we do", "services"),
    ("What makes us different", "differentiators"),
    ("Our typical customer", "typical_customer"),
    ("Current offers", "current_offers"),
)


def niche_label(niche: Niche | None, other: str | None) -> str:
    """What the business is: the niche's label, or the user's own words for 'other'."""
    if niche is None:
        return ""
    if niche.key == OTHER_NICHE:
        return (other or "").strip() or niche.label
    return niche.label


def profile_note(business_profile: dict[str, Any], niche: Niche | None, other: str | None) -> str:
    """The business profile as a note. Tone is left out: it is voice, not content."""
    lines = []
    kind = niche_label(niche, other)
    if kind:
        lines.append(f"Kind of business: {kind}")
    for label, key in _PROFILE_LINES:
        value = str(business_profile.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


# Bump when details_note changes what it writes (recorded per source).
DETAILS_NOTE_EXTRACTOR = ("business_notes.details_note", "1")


def details_note(pillar: Pillar, details: str) -> tuple[str, str]:
    """(title, text) of the note holding the details the user gave for one post."""
    details = details.strip()
    first_line = details.splitlines()[0].strip()
    summary = first_line[:60] + ("…" if len(first_line) > 60 else "")
    return f"{pillar.label}: {summary}", f"{pillar.label}\n{details}"


def find_pillar(account: dict[str, Any], pillar_key: str | None) -> Pillar | None:
    """The pillar with this key in the account's niche, or None (no key, not a
    business, or the niche has no such pillar)."""
    niche = get_niche(account.get("business_niche")) if account.get("segment") == SEGMENT_BUSINESS else None
    return next((p for p in niche.pillars if p.key == pillar_key), None) if niche and pillar_key else None


def business_context(account: dict[str, Any], pillar_key: str | None = None) -> dict[str, Any] | None:
    """What the pipeline knows about a business user (PipelineState["business"]),
    or None for anyone else. With the block enabled, facts are built fresh
    from the account and kept separate from retrieved sources."""
    if account.get("segment") != SEGMENT_BUSINESS:
        return None
    niche = get_niche(account.get("business_niche"))
    profile = account.get("business_profile") or {}
    tone = TONES_BY_KEY.get(profile.get("tone") or "")
    notes = str(profile.get("tone_notes") or "").strip()
    pillar = find_pillar(account, pillar_key)
    return {
        **({"facts": profile_note(profile, niche, account.get("business_niche_other"))} if features.business_block_enabled() else {}),
        "niche": niche.key if niche else "",
        "niche_label": niche_label(niche, account.get("business_niche_other")),
        "tone": ". ".join(part for part in (tone.label if tone else "", notes) if part),
        "pillar": {"key": pillar.key, "label": pillar.label, "about": pillar.about, "needs": pillar.needs, "writable_from_profile": pillar.writable_from_profile}
        if pillar else None,
    }
