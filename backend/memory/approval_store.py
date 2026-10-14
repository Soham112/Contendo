"""Exact-text publishing reviews and approvals. Every access is user-scoped."""
from datetime import datetime, timezone

from db.supabase_client import supabase


def create_review(user_id: str, *, content: str, media: list, post_id: int | None, flags: list) -> dict:
    return supabase.table("publish_approvals").insert({
        "user_id": user_id, "content": content, "media": media, "post_id": post_id,
        "flags": flags, "accepted_flag_ids": [], "approved_at": None,
    }).execute().data[0]


def get_review(user_id: str, review_id: str | None) -> dict | None:
    if not review_id:
        return None
    rows = (supabase.table("publish_approvals").select("*")
            .eq("user_id", user_id).eq("id", review_id).execute()).data or []
    return rows[0] if rows else None


def approve(user_id: str, review_id: str, content: str, accepted: list[str]) -> dict | None:
    rows = (supabase.table("publish_approvals").update({
        "accepted_flag_ids": accepted, "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", user_id).eq("id", review_id).eq("content", content).execute()).data or []
    return rows[0] if rows else None
