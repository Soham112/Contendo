"""Analytics router — event logging and admin analytics dashboard.

POST /log-event        — fire-and-forget user event logging (protected)
GET  /admin/analytics-data — aggregated analytics for admin dashboard (admin-only)
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from db.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


# ── Pydantic models ──────────────────────────────────────────────────────────

class LogEventRequest(BaseModel):
    event_type: str  # page_view | button_click | feature_start | feature_complete | feature_abandon
    page_url: str | None = None
    button_name: str | None = None
    metadata: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_admin(x_admin_secret: str | None) -> None:
    if not _ADMIN_SECRET or x_admin_secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


async def _insert_event(user_id: str, payload: LogEventRequest) -> None:
    """Fire-and-forget Supabase insert — all exceptions are swallowed."""
    try:
        supabase.table("user_events").insert({
            "user_id": user_id,
            "event_type": payload.event_type,
            "page_url": payload.page_url,
            "button_name": payload.button_name,
            "metadata": payload.metadata,
        }).execute()
    except Exception:
        logger.exception("analytics: failed to insert user_event")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/log-event")
async def log_event(
    body: LogEventRequest,
    user_id: str = Depends(get_user_id_dep),
) -> dict:
    """Log a user interaction event. Fire-and-forget — never blocks the caller."""
    asyncio.create_task(_insert_event(user_id, body))
    return {"logged": True}


@router.get("/admin/analytics-data")
async def get_analytics_data(
    days: int = Query(default=30, ge=1, le=365),
    x_admin_secret: str | None = Header(None),
) -> dict:
    """Return aggregated analytics from the user_events table. Admin-only."""
    _check_admin(x_admin_secret)

    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    start_date = (now - timedelta(days=days)).date().isoformat()
    end_date = now.date().isoformat()

    rows = (
        supabase.table("user_events")
        .select("user_id,event_type,page_url,button_name,metadata,timestamp")
        .gte("timestamp", since)
        .execute()
        .data
    )

    if not rows:
        return {
            "total_events": 0,
            "unique_users": 0,
            "date_range": {"start": start_date, "end": end_date},
            "event_breakdown": [],
            "page_views": [],
            "button_clicks": [],
            "feature_funnels": {},
            "daily_events": [],
            "retention": {},
        }

    total_events = len(rows)
    unique_users = len({r["user_id"] for r in rows})

    # ── Event breakdown ───────────────────────────────────────────────────────
    event_counts: dict[str, set] = {}
    for r in rows:
        et = r["event_type"] or "unknown"
        if et not in event_counts:
            event_counts[et] = set()
        event_counts[et].add(r["user_id"])

    event_breakdown = [
        {
            "event_type": et,
            "count": sum(1 for r in rows if r["event_type"] == et),
            "unique_users": len(users),
            "percentage": round(sum(1 for r in rows if r["event_type"] == et) / total_events * 100, 1),
        }
        for et, users in sorted(event_counts.items(), key=lambda x: -len(x[1]))
    ]

    # ── Page views ────────────────────────────────────────────────────────────
    page_rows = [r for r in rows if r["event_type"] == "page_view" and r.get("page_url")]
    page_counts: dict[str, set] = {}
    for r in page_rows:
        url = r["page_url"]
        if url not in page_counts:
            page_counts[url] = set()
        page_counts[url].add(r["user_id"])

    total_page_views = len(page_rows)
    page_views = [
        {
            "page_url": url,
            "count": sum(1 for r in page_rows if r["page_url"] == url),
            "unique_users": len(users),
            "percentage": round(
                sum(1 for r in page_rows if r["page_url"] == url) / total_page_views * 100, 1
            ) if total_page_views else 0,
        }
        for url, users in sorted(page_counts.items(), key=lambda x: -len(x[1]))
    ]

    # ── Button clicks ─────────────────────────────────────────────────────────
    click_rows = [r for r in rows if r["event_type"] == "button_click" and r.get("button_name")]
    btn_counts: dict[str, set] = {}
    for r in click_rows:
        btn = r["button_name"]
        if btn not in btn_counts:
            btn_counts[btn] = set()
        btn_counts[btn].add(r["user_id"])

    total_clicks = len(click_rows)
    button_clicks = [
        {
            "button_name": btn,
            "count": sum(1 for r in click_rows if r["button_name"] == btn),
            "unique_users": len(users),
            "percentage": round(
                sum(1 for r in click_rows if r["button_name"] == btn) / total_clicks * 100, 1
            ) if total_clicks else 0,
        }
        for btn, users in sorted(btn_counts.items(), key=lambda x: -len(x[1]))
    ]

    # ── Feature funnels ───────────────────────────────────────────────────────
    # First-post flow: track steps 0–5 + complete
    fp_rows = [r for r in rows if r.get("page_url") == "/first-post"]
    first_post_funnel: dict[str, int] = {}
    for r in fp_rows:
        meta = r.get("metadata") or {}
        step = meta.get("step")
        if r["event_type"] == "feature_complete" and step is None:
            key = "step_complete"
        elif step is not None:
            key = f"step_{step}"
            first_post_funnel[key] = first_post_funnel.get(key, 0) + 1
            continue
        else:
            continue
        first_post_funnel[key] = first_post_funnel.get(key, 0) + 1

    # Feed memory tour
    fm_rows = [r for r in rows if r.get("button_name") == "feed_memory_tour"]
    fm_shown = sum(1 for r in fm_rows if r["event_type"] == "feature_start")
    fm_completed = sum(1 for r in fm_rows if r["event_type"] == "feature_complete")
    fm_skipped = sum(1 for r in fm_rows if r["event_type"] == "feature_abandon")

    feature_funnels = {
        "first_post_flow": first_post_funnel,
        "feed_memory": {
            "shown": fm_shown,
            "completed": fm_completed,
            "skipped": fm_skipped,
            "completion_rate": round(fm_completed / fm_shown, 2) if fm_shown else 0,
        },
    }

    # ── Daily events ──────────────────────────────────────────────────────────
    day_counts: dict[str, int] = {}
    for r in rows:
        ts = r.get("timestamp") or ""
        day = ts[:10]
        if day:
            day_counts[day] = day_counts.get(day, 0) + 1

    daily_events = []
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date().isoformat()
        daily_events.append({"date": d, "count": day_counts.get(d, 0)})

    # ── Retention (based on post history, approximated from log-post events) ──
    # We check how many users generated posts (via button_click on generate_btn)
    gen_rows = [r for r in rows if r.get("button_name") == "generate_btn"]
    user_gen_counts: dict[str, int] = {}
    for r in gen_rows:
        uid = r["user_id"]
        user_gen_counts[uid] = user_gen_counts.get(uid, 0) + 1

    cohort_1 = sum(1 for c in user_gen_counts.values() if c >= 1)
    cohort_2 = sum(1 for c in user_gen_counts.values() if c >= 2)
    cohort_5 = sum(1 for c in user_gen_counts.values() if c >= 5)

    retention = {
        "cohort_1_post": cohort_1,
        "cohort_2_posts": cohort_2,
        "cohort_5_posts": cohort_5,
        "retention_rate_2plus": round(cohort_2 / cohort_1, 2) if cohort_1 else 0,
    }

    return {
        "total_events": total_events,
        "unique_users": unique_users,
        "date_range": {"start": start_date, "end": end_date},
        "event_breakdown": event_breakdown,
        "page_views": page_views,
        "button_clicks": button_clicks,
        "feature_funnels": feature_funnels,
        "daily_events": daily_events,
        "retention": retention,
    }
