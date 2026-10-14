"""Applying Stripe webhook events.

The one rule: our copy of a subscription is whatever Stripe says it is now.
Every event that concerns a subscription leads to the same step: fetch that
subscription from Stripe and store it. So events that arrive late, twice or
out of order all end in the right state, and nothing an event's own payload
says about status is trusted over the fetch.

Handled: checkout.session.completed, customer.subscription.created / updated /
deleted / trial_will_end, invoice.paid, invoice.payment_failed. Any other type
is acknowledged and ignored.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from billing import stripe_gateway
from billing.entitlements import ENDED_STATUSES
from memory import billing_store
from memory.publish_store import cancel_pending_jobs
from publishing.types import ErrorCode

logger = logging.getLogger(__name__)

_SUBSCRIPTION_EVENTS = frozenset({
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
})
_INVOICE_EVENTS = frozenset({"invoice.paid", "invoice.payment_failed"})
HANDLED_EVENTS = _SUBSCRIPTION_EVENTS | _INVOICE_EVENTS | {"checkout.session.completed"}


class UnknownCustomer(Exception):
    """An event names a subscription whose user we cannot identify."""


def _timestamp(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None


def _period_end(subscription: dict[str, Any]) -> int | None:
    """current_period_end is on the subscription in older API versions and on
    its items in newer ones."""
    if subscription.get("current_period_end"):
        return subscription["current_period_end"]
    items = (subscription.get("items") or {}).get("data") or []
    return items[0].get("current_period_end") if items else None


def _price_id(subscription: dict[str, Any]) -> str | None:
    items = (subscription.get("items") or {}).get("data") or []
    return ((items[0].get("price") or {}).get("id")) if items else None


def _invoice_subscription_id(invoice: dict[str, Any]) -> str | None:
    """The subscription an invoice bills: a top-level field in older API
    versions, under parent.subscription_details in newer ones."""
    direct = invoice.get("subscription")
    if direct:
        return direct if isinstance(direct, str) else direct.get("id")
    details = ((invoice.get("parent") or {}).get("subscription_details") or {})
    nested = details.get("subscription")
    return nested if isinstance(nested, str) or nested is None else nested.get("id")


def _subscription_id(event_type: str, data: dict[str, Any]) -> str | None:
    if event_type in _SUBSCRIPTION_EVENTS:
        return data.get("id")
    if event_type in _INVOICE_EVENTS:
        return _invoice_subscription_id(data)
    subscription = data.get("subscription")  # checkout.session.completed
    return subscription if isinstance(subscription, str) or subscription is None else subscription.get("id")


def sync_subscription(subscription_id: str, hinted_user_id: str | None = None) -> str:
    """Fetch the subscription from Stripe and store it; returns the user id.
    The user is the one in the subscription's metadata (set at Checkout), else
    the owner of its customer, else hinted_user_id (Checkout's client_reference_id)."""
    subscription = stripe_gateway.retrieve_subscription(subscription_id)
    customer = subscription.get("customer")
    customer_id = customer if isinstance(customer, str) else (customer or {}).get("id")
    user_id = (
        (subscription.get("metadata") or {}).get("user_id")
        or (billing_store.get_user_id_for_customer(customer_id) if customer_id else None)
        or hinted_user_id
    )
    if not user_id:
        raise UnknownCustomer(f"no user for subscription {subscription_id}")

    status = subscription.get("status")
    billing_store.save_subscription(user_id, {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription.get("id"),
        "status": status,
        "price_id": _price_id(subscription),
        "current_period_end": _timestamp(_period_end(subscription)),
        "trial_end": _timestamp(subscription.get("trial_end")),
        "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
    })
    if status in ENDED_STATUSES:
        # Stripe's grace period is over: nothing still scheduled will go out.
        cancelled = cancel_pending_jobs(user_id, ErrorCode.SUBSCRIPTION_ENDED)
        logger.info("subscription %s ended for user %s: cancelled %d pending publish jobs",
                    subscription_id, user_id, cancelled)
    return user_id


def handle_event(event: dict[str, Any]) -> str:
    """Apply one verified event. Returns "ignored" (a type we do not handle, or
    one with no subscription), "duplicate" (already handled) or "processed".
    Raises if handling fails; the event is then forgotten so Stripe's retry runs."""
    event_id, event_type = event["id"], event["type"]
    if event_type not in HANDLED_EVENTS:
        return "ignored"
    if not billing_store.claim_event(event_id, event_type):
        return "duplicate"
    try:
        data = (event.get("data") or {}).get("object") or {}
        subscription_id = _subscription_id(event_type, data)
        if not subscription_id:
            return "ignored"  # e.g. an invoice for a one-off charge
        sync_subscription(subscription_id, hinted_user_id=data.get("client_reference_id"))
    except Exception:
        billing_store.release_event(event_id)
        raise
    return "processed"
