"""Admin router — usage analytics endpoint.

All routes require the x-admin-secret header to match the ADMIN_SECRET env var.
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from db.supabase_client import supabase

router = APIRouter(prefix="/admin")

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def _check_admin(x_admin_secret: str | None) -> None:
    if not _ADMIN_SECRET or x_admin_secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/usage")
async def get_usage(x_admin_secret: str | None = Header(None)) -> dict:
    """Return aggregated usage stats from the usage_events table."""
    _check_admin(x_admin_secret)

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    week_since = (now - timedelta(days=7)).isoformat()
    since_14d = (now - timedelta(days=14)).isoformat()

    # Pull all events in one query — small table, acceptable for a personal project
    all_rows = (
        supabase.table("usage_events")
        .select("user_id,input_tokens,output_tokens,estimated_cost_usd,created_at")
        .execute()
        .data
    )

    # ── Totals ────────────────────────────────────────────────────────────────
    total_calls = len(all_rows)
    total_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in all_rows)

    today_rows = [r for r in all_rows if r["created_at"][:10] == today_str]
    today_calls = len(today_rows)
    today_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in today_rows)

    week_rows = [r for r in all_rows if r["created_at"] >= week_since]
    week_calls = len(week_rows)
    week_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in week_rows)

    # ── Distinct users ────────────────────────────────────────────────────────
    distinct_users = len({r["user_id"] for r in all_rows})

    # ── Daily call counts for last 14 days ────────────────────────────────────
    recent_rows = [r for r in all_rows if r["created_at"] >= since_14d]
    day_counts: dict[str, int] = {}
    for r in recent_rows:
        day = r["created_at"][:10]
        day_counts[day] = day_counts.get(day, 0) + 1

    # Fill in zero-count days so the chart has a continuous x-axis
    daily = []
    for i in range(14):
        d = (now - timedelta(days=13 - i)).date().isoformat()
        daily.append({"date": d, "count": day_counts.get(d, 0)})

    # ── Per-user aggregates ───────────────────────────────────────────────────
    user_agg: dict[str, dict] = {}
    for r in all_rows:
        uid = r["user_id"]
        if uid not in user_agg:
            user_agg[uid] = {"call_count": 0, "total_tokens": 0, "total_cost": 0.0}
        user_agg[uid]["call_count"] += 1
        user_agg[uid]["total_tokens"] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
        user_agg[uid]["total_cost"] += float(r.get("estimated_cost_usd") or 0)

    top_users = sorted(
        [{"user_id": uid, **data} for uid, data in user_agg.items()],
        key=lambda x: x["total_cost"],
        reverse=True,
    )

    return {
        "distinct_users": distinct_users,
        "calls": {
            "today": today_calls,
            "this_week": week_calls,
            "all_time": total_calls,
        },
        "cost_usd": {
            "today": round(today_cost, 6),
            "this_week": round(week_cost, 6),
            "all_time": round(total_cost, 6),
        },
        "daily": daily,
        "top_users": top_users,
    }
