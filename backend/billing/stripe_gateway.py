"""Every call to Stripe. Nothing else in the backend imports the stripe SDK,
so tests replace these functions and no test reaches Stripe.

Settings (all required for billing; see config() below):
  STRIPE_SECRET_KEY      sk_test_... locally, sk_live_... in production
  STRIPE_WEBHOOK_SECRET  whsec_... of the webhook endpoint (or of `stripe listen`)
  STRIPE_PRICE_ID_PRO    the recurring Price of the Pro plan
  STRIPE_TRIAL_DAYS      free-trial length in days (default 7)
  FRONTEND_ORIGIN        where Checkout and the portal send the user back to
"""

import os
from dataclasses import dataclass
from typing import Any

import stripe

DEFAULT_TRIAL_DAYS = 7


class BillingConfigError(RuntimeError):
    """A Stripe setting is missing, so billing cannot run."""


@dataclass(frozen=True)
class StripeConfig:
    secret_key: str
    webhook_secret: str
    price_id: str
    trial_days: int
    frontend_origin: str


# "1" turns billing off on purpose, e.g. before the Stripe account exists. The
# app then runs on the free plan only: Checkout, the portal and the webhook
# answer 503, and the upgrade screens say Pro can't be bought yet.
DISABLED_ENV = "BILLING_DISABLED"


def billing_disabled() -> bool:
    """True only when BILLING_DISABLED is exactly "1"."""
    return os.environ.get(DISABLED_ENV, "").strip() == "1"


def checkout_available() -> bool:
    """Whether a user can start Checkout: billing on and fully configured."""
    try:
        config()
    except BillingConfigError:
        return False
    return True


def config() -> StripeConfig:
    """Read on every call, like config.security.current()."""
    if billing_disabled():
        raise BillingConfigError(f"Billing is turned off ({DISABLED_ENV}=1).")
    values = {name: os.environ.get(name, "").strip()
              for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID_PRO", "FRONTEND_ORIGIN")}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise BillingConfigError(f"Billing is not configured: set {', '.join(missing)}.")
    trial = os.environ.get("STRIPE_TRIAL_DAYS", "").strip()
    return StripeConfig(
        secret_key=values["STRIPE_SECRET_KEY"],
        webhook_secret=values["STRIPE_WEBHOOK_SECRET"],
        price_id=values["STRIPE_PRICE_ID_PRO"],
        trial_days=int(trial) if trial else DEFAULT_TRIAL_DAYS,
        frontend_origin=values["FRONTEND_ORIGIN"].rstrip("/"),
    )


def _client():
    return stripe.StripeClient(config().secret_key).v1


def create_customer(user_id: str) -> str:
    """A Stripe customer for this user; returns its id. Checkout collects the email."""
    customer = _client().customers.create(params={"metadata": {"user_id": user_id}})
    return customer.id


def create_checkout_session(customer_id: str, user_id: str) -> str:
    """A Checkout session for the Pro subscription, with the trial; returns its URL.
    user_id travels in the subscription's metadata so webhooks can find the user."""
    settings = config()
    session = _client().checkout.sessions.create(params={
        "mode": "subscription",
        "customer": customer_id,
        "client_reference_id": user_id,
        "line_items": [{"price": settings.price_id, "quantity": 1}],
        "subscription_data": {
            "trial_period_days": settings.trial_days,
            "metadata": {"user_id": user_id},
        },
        "success_url": f"{settings.frontend_origin}/settings/billing?checkout=success",
        "cancel_url": f"{settings.frontend_origin}/settings/billing?checkout=cancelled",
    })
    return session.url


def create_portal_session(customer_id: str) -> str:
    """A Customer Portal session (cancel, payment method, invoices); returns its URL."""
    session = _client().billing_portal.sessions.create(params={
        "customer": customer_id,
        "return_url": f"{config().frontend_origin}/settings/billing",
    })
    return session.url


def retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    """The subscription as Stripe has it now, as a plain dict."""
    return _client().subscriptions.retrieve(subscription_id).to_dict()


def retrieve_price() -> dict[str, Any]:
    """The Pro price for display: {amount, currency, interval, trial_days}.
    amount is in the currency's smallest unit."""
    settings = config()
    price = _client().prices.retrieve(settings.price_id)
    return {
        "amount": price.unit_amount,
        "currency": price.currency,
        "interval": price.recurring.interval if price.recurring else None,
        "trial_days": settings.trial_days,
    }


def construct_event(body: bytes, signature: str | None) -> dict[str, Any]:
    """Verify a webhook's signature and return the event as a plain dict.
    Raises ValueError when the signature is missing or does not verify."""
    try:
        event = stripe.Webhook.construct_event(body, signature, config().webhook_secret)
    except stripe.SignatureVerificationError as exc:
        raise ValueError("Stripe signature verification failed") from exc
    return event.to_dict()
