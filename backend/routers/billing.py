"""Billing endpoints: entitlements, plans, Stripe Checkout and portal, and the
Stripe webhook."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from auth.supabase_jwt import get_user_id_dep
from billing import entitlements as plans
from billing import stripe_gateway, webhooks
from billing.stripe_gateway import BillingConfigError
from memory import billing_store

logger = logging.getLogger(__name__)

router = APIRouter()

_UNAVAILABLE = "Billing isn't available right now. Please try again later."
# The Pro price changes rarely; fetching it from Stripe on every page view would not.
_PRICE_TTL_SECONDS = 600
_price_cache: tuple[float, dict] | None = None


def _pro_price() -> dict | None:
    """The Pro price as Stripe has it, or None when it cannot be read (billing
    not configured, Stripe unreachable). Never a hard-coded amount."""
    global _price_cache
    if _price_cache and time.monotonic() - _price_cache[0] < _PRICE_TTL_SECONDS:
        return _price_cache[1]
    try:
        price = stripe_gateway.retrieve_price()
    except BillingConfigError:
        return None
    except Exception:
        logger.exception("GET /billing/plans: could not read the Pro price from Stripe")
        return None
    _price_cache = (time.monotonic(), price)
    return price


@router.get("/billing/plans")
def get_plans() -> dict:
    """Public: what each plan includes and what Pro costs. The landing pages and
    the upgrade screen show these and never a figure of their own."""
    return {
        "free": {"generations_per_month": plans.FREE_GENERATIONS_PER_MONTH, "publishing": False},
        "pro": {
            "generations_per_month": plans.PRO_GENERATIONS_PER_MONTH,
            "publishing": True,
            "max_accounts_per_platform": plans.PRO_MAX_ACCOUNTS_PER_PLATFORM,
            "price": _pro_price(),
        },
    }


@router.get("/billing/entitlements")
def read_entitlements(user_id: str = Depends(get_user_id_dep)) -> dict:
    return plans.get_entitlements(user_id).to_dict()


@router.post("/billing/checkout")
def start_checkout(user_id: str = Depends(get_user_id_dep)) -> dict:
    """A Stripe Checkout URL for the Pro plan. The plan itself changes only
    when Stripe's webhook says the subscription exists."""
    if plans.get_entitlements(user_id).plan == plans.PLAN_PRO:
        raise HTTPException(status_code=409, detail="You're already on the Pro plan.")
    try:
        subscription = billing_store.get_subscription(user_id) or {}
        customer_id = subscription.get("stripe_customer_id")
        if not customer_id:
            customer_id = stripe_gateway.create_customer(user_id)
            billing_store.save_customer(user_id, customer_id)
        return {"url": stripe_gateway.create_checkout_session(customer_id, user_id)}
    except BillingConfigError:
        logger.error("POST /billing/checkout: billing is not configured")
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    except Exception:
        logger.exception("POST /billing/checkout failed for user %s", user_id)
        raise HTTPException(status_code=502, detail=_UNAVAILABLE)


@router.post("/billing/portal")
def open_portal(user_id: str = Depends(get_user_id_dep)) -> dict:
    """A Stripe Customer Portal URL: cancel, change payment method, invoices."""
    customer_id = (billing_store.get_subscription(user_id) or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="You don't have a subscription to manage yet.")
    try:
        return {"url": stripe_gateway.create_portal_session(customer_id)}
    except BillingConfigError:
        logger.error("POST /billing/portal: billing is not configured")
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    except Exception:
        logger.exception("POST /billing/portal failed for user %s", user_id)
        raise HTTPException(status_code=502, detail=_UNAVAILABLE)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> dict:
    """Public, and trusted only through Stripe's signature over the raw body.
    A 4xx tells Stripe not to retry; a 5xx asks it to."""
    body = await request.body()
    try:
        event = stripe_gateway.construct_event(body, request.headers.get("stripe-signature"))
    except BillingConfigError:
        logger.error("POST /billing/webhook: billing is not configured")
        raise HTTPException(status_code=503, detail="Billing is not configured")
    except ValueError:
        logger.warning("POST /billing/webhook: signature rejected")
        raise HTTPException(status_code=400, detail="Invalid signature")
    try:
        outcome = await run_in_threadpool(webhooks.handle_event, event)
    except webhooks.UnknownCustomer:
        # Not ours to act on (another product on the same Stripe account).
        logger.warning("POST /billing/webhook: %s %s names no known user", event.get("type"), event.get("id"))
        return {"received": True, "outcome": "ignored"}
    except Exception:
        logger.exception("POST /billing/webhook: handling %s %s failed", event.get("type"), event.get("id"))
        raise HTTPException(status_code=500, detail="Webhook handling failed")
    return {"received": True, "outcome": outcome}
