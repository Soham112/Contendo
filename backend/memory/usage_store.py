"""Usage event logging — fire-and-forget writes to Supabase usage_events table.

Never raises. Wrap all call sites in asyncio.get_running_loop().create_task().
"""
import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Cost per token (USD) — Sonnet and Haiku pricing
_SONNET_INPUT = 0.000003
_SONNET_OUTPUT = 0.000015
_HAIKU_INPUT = 0.00000025
_HAIKU_OUTPUT = 0.00000125


def _calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    if model == "haiku":
        return (input_tokens * _HAIKU_INPUT) + (output_tokens * _HAIKU_OUTPUT)
    return (input_tokens * _SONNET_INPUT) + (output_tokens * _SONNET_OUTPUT)


async def _insert_event(payload: dict) -> None:
    if not _SUPABASE_URL or not _SUPABASE_SERVICE_ROLE_KEY:
        logger.debug("usage_store: Supabase not configured, skipping usage log")
        return
    url = f"{_SUPABASE_URL}/rest/v1/usage_events"
    headers = {
        "apikey": _SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {_SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.warning(
                "usage_store: insert failed status=%d body=%s",
                resp.status_code,
                resp.text[:200],
            )


async def log_usage_event(
    user_id: str,
    event_type: str,
    input_tokens: int,
    output_tokens: int,
    metadata: dict[str, Any] | None = None,
    model: str = "sonnet",
) -> None:
    """Log one Claude API call to Supabase. Never raises — safe for create_task()."""
    try:
        cost = _calculate_cost(input_tokens, output_tokens, model)
        payload = {
            "user_id": user_id,
            "event_type": event_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": float(cost),
            "metadata": metadata or {},
        }
        await _insert_event(payload)
    except Exception as exc:
        logger.warning("usage_store: unhandled error: %s", exc)
