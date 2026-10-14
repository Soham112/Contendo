"""The accounts table: who a user creates content for (migration 007).

One row per user, keyed by user_id. A user with no row has not answered the
segment question yet.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from db.supabase_client import supabase

# After "Skip for now", the segment question is asked again this many days later.
SEGMENT_REASK_DAYS = 7

_COLUMNS = "user_id,segment,business_niche,business_niche_other,business_profile,segment_skipped_at"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_account(user_id: str) -> dict[str, Any]:
    """The user's account row, or the same shape with every value None when
    they have none yet."""
    rows = supabase.table("accounts").select(_COLUMNS).eq("user_id", user_id).execute().data or []
    if rows:
        return rows[0]
    return {
        "user_id": user_id,
        "segment": None,
        "business_niche": None,
        "business_niche_other": None,
        "business_profile": None,
        "segment_skipped_at": None,
    }


def should_ask_segment(account: dict[str, Any], now: datetime | None = None) -> bool:
    """Whether to show the segment question: unanswered, and either never
    skipped or skipped at least SEGMENT_REASK_DAYS ago."""
    if account.get("segment"):
        return False
    skipped_at = account.get("segment_skipped_at")
    if not skipped_at:
        return True
    return (now or _now()) - datetime.fromisoformat(skipped_at) >= timedelta(days=SEGMENT_REASK_DAYS)


def save_segment(
    user_id: str,
    segment: str,
    business_niche: str | None = None,
    business_niche_other: str | None = None,
    business_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record the user's answer. The business fields are stored as given, so an
    individual's row carries None for all three."""
    row = {
        "user_id": user_id,
        "segment": segment,
        "business_niche": business_niche,
        "business_niche_other": business_niche_other,
        "business_profile": business_profile,
        "updated_at": _now().isoformat(),
    }
    supabase.table("accounts").upsert(row, on_conflict="user_id").execute()
    return get_account(user_id)


def mark_segment_skipped(user_id: str) -> dict[str, Any]:
    """Record "Skip for now". An answer already given is left as it is."""
    now = _now().isoformat()
    supabase.table("accounts").upsert(
        {"user_id": user_id, "segment_skipped_at": now, "updated_at": now},
        on_conflict="user_id",
    ).execute()
    return get_account(user_id)
