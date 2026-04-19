from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase


# ---------------------------------------------------------------------------
# No-op init functions — tables already exist in Supabase
# ---------------------------------------------------------------------------

def init_db() -> None:
    pass


def init_retrieval_stats_db() -> None:
    pass


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

def log_post(
    topic: str,
    format: str,
    tone: str,
    content: str,
    authenticity_score: int,
    svg_diagrams: str | None = None,
    archetype: str = "",
    user_id: str = "default",
) -> int:
    result = supabase.table("posts").insert({
        "topic": topic,
        "format": format,
        "tone": tone,
        "content": content,
        "authenticity_score": authenticity_score,
        "svg_diagrams": svg_diagrams,
        "archetype": archetype,
        "user_id": user_id,
    }).execute()
    return result.data[0]["id"] if result.data else 0


def get_recent_posts(user_id: str = "default", limit: int = 20) -> list[dict[str, Any]]:
    result = (
        supabase.table("posts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_all_topics_posted(user_id: str = "default") -> list[str]:
    result = (
        supabase.table("posts")
        .select("topic")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [row["topic"] for row in (result.data or [])]


_UNSET = object()


def update_post(
    post_id: int,
    user_id: str = "default",
    content=_UNSET,
    authenticity_score=_UNSET,
    svg_diagrams=_UNSET,
) -> bool:
    """Update only the fields that are explicitly provided. _UNSET means skip that field."""
    update_data: dict[str, Any] = {}
    if content is not _UNSET:
        update_data["content"] = content
    if authenticity_score is not _UNSET:
        update_data["authenticity_score"] = authenticity_score
    if svg_diagrams is not _UNSET:
        update_data["svg_diagrams"] = svg_diagrams
    if not update_data:
        return False
    result = (
        supabase.table("posts")
        .update(update_data)
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def delete_post(post_id: int, user_id: str = "default") -> bool:
    result = (
        supabase.table("posts")
        .delete()
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def mark_published(
    post_id: int,
    platform: str,
    published_content: str | None = None,
    user_id: str = "default",
) -> bool:
    ownership = (
        supabase.table("posts")
        .select("id")
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not ownership.data:
        return False
    result = (
        supabase.table("posts")
        .update({
            "published_at": datetime.now(timezone.utc).isoformat(),
            "published_platform": platform,
            "published_content": published_content,
        })
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


# ---------------------------------------------------------------------------
# Post versions
# ---------------------------------------------------------------------------

def _post_owned_by(post_id: int, user_id: str) -> bool:
    result = (
        supabase.table("posts")
        .select("id")
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def add_version(
    post_id: int,
    content: str,
    authenticity_score: int | None,
    version_type: str,
    svg_diagrams: str | None = None,
    user_id: str = "default",
) -> int:
    """Insert a new version row for post_id. version_number is auto-incremented per post."""
    if not _post_owned_by(post_id, user_id):
        return 0
    max_v = (
        supabase.table("post_versions")
        .select("version_number")
        .eq("post_id", post_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    next_version = (max_v.data[0]["version_number"] if max_v.data else 0) + 1
    result = supabase.table("post_versions").insert({
        "post_id": post_id,
        "version_number": next_version,
        "content": content,
        "authenticity_score": authenticity_score,
        "version_type": version_type,
        "svg_diagrams": svg_diagrams,
    }).execute()
    return result.data[0]["id"] if result.data else 0


def get_versions(post_id: int, user_id: str = "default") -> list[dict[str, Any]]:
    """Return all versions for a post ordered by version_number ascending."""
    if not _post_owned_by(post_id, user_id):
        return []
    result = (
        supabase.table("post_versions")
        .select("*")
        .eq("post_id", post_id)
        .order("version_number", desc=False)
        .execute()
    )
    return result.data or []


def get_best_version(post_id: int, user_id: str = "default") -> dict[str, Any] | None:
    """Return the version with the highest authenticity_score; latest version breaks ties."""
    if not _post_owned_by(post_id, user_id):
        return None
    result = (
        supabase.table("post_versions")
        .select("*")
        .eq("post_id", post_id)
        .order("authenticity_score", desc=True)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def restore_version(post_id: int, version_id: int, user_id: str = "default") -> bool:
    """Restore a post's content to match a specific version."""
    version = (
        supabase.table("post_versions")
        .select("*")
        .eq("id", version_id)
        .eq("post_id", post_id)
        .execute()
    )
    if not version.data:
        return False
    v = version.data[0]
    update_data: dict[str, Any] = {"content": v["content"]}
    if v.get("authenticity_score") is not None:
        update_data["authenticity_score"] = v["authenticity_score"]
    if v.get("svg_diagrams") is not None:
        update_data["svg_diagrams"] = v["svg_diagrams"]
    result = (
        supabase.table("posts")
        .update(update_data)
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def update_latest_version_svg(post_id: int, svg_diagrams: str | None, user_id: str = "default") -> bool:
    """Update svg_diagrams on the most recent version row without creating a new version."""
    if not _post_owned_by(post_id, user_id):
        return False
    max_v = (
        supabase.table("post_versions")
        .select("version_number")
        .eq("post_id", post_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    if not max_v.data:
        return False
    max_version = max_v.data[0]["version_number"]
    result = (
        supabase.table("post_versions")
        .update({"svg_diagrams": svg_diagrams})
        .eq("post_id", post_id)
        .eq("version_number", max_version)
        .execute()
    )
    return len(result.data) > 0


# ---------------------------------------------------------------------------
# Retrieval stats
# ---------------------------------------------------------------------------

def increment_retrieval(user_id: str = "default", source_title: str = "") -> None:
    try:
        existing = (
            supabase.table("source_retrieval_stats")
            .select("retrieval_count")
            .eq("user_id", user_id)
            .eq("source_title", source_title)
            .execute()
        )
        now = datetime.now(timezone.utc).isoformat()
        if existing.data:
            new_count = existing.data[0]["retrieval_count"] + 1
            supabase.table("source_retrieval_stats").update({
                "retrieval_count": new_count,
                "last_retrieved_at": now,
            }).eq("user_id", user_id).eq("source_title", source_title).execute()
        else:
            supabase.table("source_retrieval_stats").insert({
                "user_id": user_id,
                "source_title": source_title,
                "retrieval_count": 1,
                "last_retrieved_at": now,
            }).execute()
    except Exception:
        pass  # non-critical stat tracking


def get_retrieval_counts(user_id: str = "default") -> dict[str, int]:
    result = (
        supabase.table("source_retrieval_stats")
        .select("source_title,retrieval_count")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["source_title"]: row["retrieval_count"] for row in (result.data or [])}
