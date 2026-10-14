"""Quota, entitlements, checkout and the Stripe webhook. Stripe itself is never
called: billing.stripe_gateway's functions are replaced, except construct_event,
whose real signature check runs against a test secret."""

import hashlib
import hmac
import json
import time

import pytest

WEBHOOK_SECRET = "whsec_test_secret"
PRICE_ID = "price_pro_test"


@pytest.fixture
def a_headers(client, production, auth_headers):
    return auth_headers("user-a")


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", PRICE_ID)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example")


@pytest.fixture
def stripe_state(monkeypatch, stripe_env):
    """Stripe's side: the subscriptions it would return, and the calls made to it."""
    from billing import stripe_gateway

    state = {"subscriptions": {}, "customers": [], "checkouts": [], "portals": [], "retrieved": []}

    def create_customer(user_id):
        state["customers"].append(user_id)
        return f"cus_{user_id}"

    def create_checkout_session(customer_id, user_id):
        state["checkouts"].append((customer_id, user_id))
        return "https://checkout.stripe.test/session"

    def create_portal_session(customer_id):
        state["portals"].append(customer_id)
        return "https://billing.stripe.test/portal"

    def retrieve_subscription(subscription_id):
        state["retrieved"].append(subscription_id)
        return state["subscriptions"][subscription_id]

    monkeypatch.setattr(stripe_gateway, "create_customer", create_customer)
    monkeypatch.setattr(stripe_gateway, "create_checkout_session", create_checkout_session)
    monkeypatch.setattr(stripe_gateway, "create_portal_session", create_portal_session)
    monkeypatch.setattr(stripe_gateway, "retrieve_subscription", retrieve_subscription)
    monkeypatch.setattr(stripe_gateway, "retrieve_price", lambda: {
        "amount": 3900, "currency": "usd", "interval": "month", "trial_days": 7})
    return state


def subscription(status="trialing", user_id="user-a", sub_id="sub_1", **extra):
    return {
        "id": sub_id, "customer": f"cus_{user_id}", "status": status,
        "metadata": {"user_id": user_id} if user_id else {},
        "trial_end": 1_800_000_000 if status == "trialing" else None,
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"id": PRICE_ID}, "current_period_end": 1_800_000_000}]},
        **extra,
    }


def signed(event: dict, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    timestamp = timestamp or int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={timestamp},v1={signature}", "content-type": "application/json"}


def event(event_type: str, obj: dict, event_id: str = "evt_1") -> dict:
    return {"id": event_id, "object": "event", "type": event_type, "data": {"object": obj}}


def post_event(client, evt: dict, **kwargs):
    body, headers = signed(evt, **kwargs)
    return client.post("/billing/webhook", content=body, headers=headers)


def make_pro(fake_db, user_id="user-a", status="active"):
    fake_db.tables.setdefault("subscriptions", []).append({
        "user_id": user_id, "stripe_customer_id": f"cus_{user_id}", "stripe_subscription_id": "sub_1",
        "status": status, "current_period_end": "2027-01-01T00:00:00+00:00",
        "trial_end": "2026-11-01T00:00:00+00:00", "cancel_at_period_end": False,
    })


# --- Entitlements ---------------------------------------------------------------

def test_a_new_user_is_on_the_free_plan(client, a_headers):
    body = client.get("/billing/entitlements", headers=a_headers).json()
    assert body["plan"] == "free"
    assert body["generation_limit"] == 10 and body["generations_remaining"] == 10
    assert body["can_generate"] is True
    assert body["can_publish"] is False and body["max_connected_accounts"] == 0


@pytest.mark.parametrize("status, plan, can_publish, paused", [
    ("trialing", "pro", True, False),
    ("active", "pro", True, False),
    ("past_due", "pro", False, True),     # Stripe's grace period: publishing paused
    ("canceled", "free", False, False),
    ("unpaid", "free", False, False),
    ("incomplete", "free", False, False),
    ("incomplete_expired", "free", False, False),
    ("paused", "free", False, False),
    (None, "free", False, False),         # a customer who never finished Checkout
])
def test_entitlements_follow_the_subscription_status(fake_db, status, plan, can_publish, paused):
    from billing.entitlements import get_entitlements

    make_pro(fake_db, status=status)
    entitlements = get_entitlements("user-a")
    assert (entitlements.plan, entitlements.can_publish, entitlements.publishing_paused) == (plan, can_publish, paused)
    assert (entitlements.max_connected_accounts > 0) == (plan == "pro")
    assert entitlements.generation_limit == (300 if plan == "pro" else 10)


def test_trial_end_is_reported_only_while_trialing(fake_db):
    from billing.entitlements import get_entitlements

    make_pro(fake_db, status="trialing")
    assert get_entitlements("user-a").trial_end == "2026-11-01T00:00:00+00:00"
    fake_db.tables["subscriptions"][0]["status"] = "active"
    assert get_entitlements("user-a").trial_end is None


def test_entitlements_are_per_user(fake_db):
    from billing.entitlements import get_entitlements

    make_pro(fake_db, user_id="user-a")
    assert get_entitlements("user-b").plan == "free"


# --- Generation quota -------------------------------------------------------------

@pytest.fixture
def pipeline(monkeypatch):
    """Replace run_pipeline in the route. Set result["status"] or result["raise"]."""
    import routers.generate as route

    result = {"status": "ok", "raise": None, "calls": 0}

    def fake(**kwargs):
        result["calls"] += 1
        if result["raise"]:
            raise result["raise"]
        return {"status": result["status"], "post": "A post." if result["status"] == "ok" else "",
                "score": 0, "score_feedback": [], "iterations": 1}

    monkeypatch.setattr(route, "run_pipeline", fake)
    return result


REQUEST = {"topic": "A topic", "format": "linkedin post", "tone": "casual"}


def _used(client, headers) -> int:
    return client.get("/billing/entitlements", headers=headers).json()["generations_used"]


def test_the_eleventh_free_post_is_refused(client, a_headers, pipeline):
    for _ in range(10):
        assert client.post("/generate", headers=a_headers, json=REQUEST).status_code == 200
    resp = client.post("/generate", headers=a_headers, json=REQUEST)

    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert detail["code"] == "quota_exceeded"
    assert "10 free posts" in detail["message"]
    assert detail["entitlements"]["generations_remaining"] == 0
    assert pipeline["calls"] == 10  # the refused request never reached the pipeline


def test_remaining_posts_count_down(client, a_headers, pipeline):
    client.post("/generate", headers=a_headers, json=REQUEST)
    client.post("/generate", headers=a_headers, json=REQUEST)
    body = client.get("/billing/entitlements", headers=a_headers).json()
    assert (body["generations_used"], body["generations_remaining"]) == (2, 8)


@pytest.mark.parametrize("status", ["low_coverage", "draft_truncated", "draft_refused", "draft_empty"])
def test_a_request_that_makes_no_post_does_not_count(client, a_headers, pipeline, status):
    pipeline["status"] = status
    assert client.post("/generate", headers=a_headers, json=REQUEST).status_code == 200
    assert _used(client, a_headers) == 0


def test_a_failed_request_does_not_count(client, a_headers, pipeline):
    pipeline["raise"] = RuntimeError("boom")
    assert client.post("/generate", headers=a_headers, json=REQUEST).status_code == 500
    assert _used(client, a_headers) == 0


def test_a_rejected_request_does_not_count(client, a_headers, pipeline):
    assert client.post("/generate", headers=a_headers, json={**REQUEST, "topic": " "}).status_code == 400
    assert client.post("/generate", headers=a_headers, json={**REQUEST, "pillar": "new_listing"}).status_code == 400
    assert _used(client, a_headers) == 0


def test_the_quota_is_per_user(client, a_headers, auth_headers, pipeline):
    for _ in range(10):
        client.post("/generate", headers=a_headers, json=REQUEST)
    assert client.post("/generate", headers=auth_headers("user-b"), json=REQUEST).status_code == 200


def test_the_quota_resets_with_the_month(client, a_headers, pipeline, fake_db):
    from memory.billing_store import current_period

    fake_db.tables["generation_usage"] = [{"user_id": "user-a", "period": "2020-01", "count": 10}]
    assert current_period() != "2020-01"
    assert client.post("/generate", headers=a_headers, json=REQUEST).status_code == 200
    assert _used(client, a_headers) == 1


def test_a_pro_user_has_the_higher_limit(client, a_headers, pipeline, fake_db):
    from memory.billing_store import current_period

    make_pro(fake_db)
    fake_db.tables["generation_usage"] = [{"user_id": "user-a", "period": current_period(), "count": 10}]
    assert client.post("/generate", headers=a_headers, json=REQUEST).status_code == 200
    fake_db.tables["generation_usage"][0]["count"] = 300
    resp = client.post("/generate", headers=a_headers, json=REQUEST)
    assert resp.status_code == 402
    assert "resets at the start of next month" in resp.json()["detail"]["message"]


def test_reserve_never_goes_past_the_limit(fake_db):
    from memory import billing_store

    assert [billing_store.reserve_generation("u", "2026-10", 2) for _ in range(4)] == [True, True, False, False]
    assert billing_store.get_generation_count("u", "2026-10") == 2
    billing_store.release_generation("u", "2026-10")
    billing_store.release_generation("u", "2026-10")
    billing_store.release_generation("u", "2026-10")  # never below zero
    assert billing_store.get_generation_count("u", "2026-10") == 0


# --- Plans, checkout, portal ------------------------------------------------------

def test_plans_are_public_and_carry_the_price_from_stripe(client, production, stripe_state, monkeypatch):
    import routers.billing as route

    monkeypatch.setattr(route, "_price_cache", None)
    body = client.get("/billing/plans").json()
    assert body["free"] == {"generations_per_month": 10, "publishing": False}
    assert body["pro"]["price"] == {"amount": 3900, "currency": "usd", "interval": "month", "trial_days": 7}


def test_plans_give_no_price_when_billing_is_not_configured(client, production, monkeypatch):
    import routers.billing as route

    monkeypatch.setattr(route, "_price_cache", None)
    resp = client.get("/billing/plans")
    assert resp.status_code == 200
    assert resp.json()["pro"]["price"] is None


def test_checkout_creates_a_customer_once_and_does_not_change_the_plan(client, a_headers, stripe_state, fake_db):
    assert client.post("/billing/checkout", headers=a_headers).json() == {"url": "https://checkout.stripe.test/session"}
    client.post("/billing/checkout", headers=a_headers)

    assert stripe_state["customers"] == ["user-a"]
    assert stripe_state["checkouts"] == [("cus_user-a", "user-a")] * 2
    assert fake_db.tables["subscriptions"][0].get("status") is None
    assert client.get("/billing/entitlements", headers=a_headers).json()["plan"] == "free"


def test_checkout_is_refused_for_a_pro_user(client, a_headers, stripe_state, fake_db):
    make_pro(fake_db)
    assert client.post("/billing/checkout", headers=a_headers).status_code == 409
    assert stripe_state["checkouts"] == []


def test_checkout_without_stripe_settings_is_a_503(client, a_headers):
    assert client.post("/billing/checkout", headers=a_headers).status_code == 503


def test_portal_needs_a_customer(client, a_headers, stripe_state, fake_db):
    assert client.post("/billing/portal", headers=a_headers).status_code == 404
    make_pro(fake_db)
    assert client.post("/billing/portal", headers=a_headers).json() == {"url": "https://billing.stripe.test/portal"}
    assert stripe_state["portals"] == ["cus_user-a"]


def test_billing_endpoints_require_a_token(client, production):
    assert client.get("/billing/entitlements").status_code == 401
    assert client.post("/billing/checkout").status_code == 401
    assert client.post("/billing/portal").status_code == 401


# --- Webhook: signature -----------------------------------------------------------

def test_a_webhook_without_a_signature_is_rejected(client, production, stripe_state, fake_db):
    resp = client.post("/billing/webhook", content=b"{}", headers={"content-type": "application/json"})
    assert resp.status_code == 400
    assert fake_db.tables.get("stripe_events", []) == []


def test_a_webhook_signed_with_another_secret_is_rejected(client, production, stripe_state, fake_db):
    stripe_state["subscriptions"]["sub_1"] = subscription()
    resp = post_event(client, event("customer.subscription.created", {"id": "sub_1"}), secret="whsec_wrong")
    assert resp.status_code == 400
    assert fake_db.tables.get("subscriptions", []) == []


def test_a_tampered_body_is_rejected(client, production, stripe_state, fake_db):
    body, headers = signed(event("customer.subscription.created", {"id": "sub_1"}))
    resp = client.post("/billing/webhook", content=body.replace(b"sub_1", b"sub_2"), headers=headers)
    assert resp.status_code == 400


def test_an_old_signature_is_rejected(client, production, stripe_state):
    resp = post_event(client, event("customer.subscription.created", {"id": "sub_1"}),
                      timestamp=int(time.time()) - 3600)
    assert resp.status_code == 400


def test_a_webhook_without_stripe_settings_is_a_503(client, production):
    assert client.post("/billing/webhook", content=b"{}").status_code == 503


# --- Webhook: each event type -----------------------------------------------------

def _row(fake_db):
    return fake_db.tables["subscriptions"][0]


def test_checkout_completed_links_the_subscription(client, production, stripe_state, fake_db):
    # The subscription has no metadata here: the user comes from client_reference_id.
    stripe_state["subscriptions"]["sub_1"] = subscription(user_id=None, customer="cus_new")
    resp = post_event(client, event("checkout.session.completed", {
        "id": "cs_1", "customer": "cus_new", "subscription": "sub_1", "client_reference_id": "user-a"}))

    assert resp.json() == {"received": True, "outcome": "processed"}
    assert _row(fake_db)["user_id"] == "user-a"
    assert _row(fake_db)["status"] == "trialing"
    assert _row(fake_db)["stripe_customer_id"] == "cus_new"
    assert _row(fake_db)["price_id"] == PRICE_ID


@pytest.mark.parametrize("event_type", [
    "customer.subscription.created", "customer.subscription.updated", "customer.subscription.trial_will_end"])
def test_subscription_events_store_what_stripe_has_now(client, production, stripe_state, fake_db, event_type):
    stripe_state["subscriptions"]["sub_1"] = subscription("trialing")
    # The event's own payload says "incomplete"; Stripe's current answer wins.
    resp = post_event(client, event(event_type, {"id": "sub_1", "status": "incomplete"}))

    assert resp.json()["outcome"] == "processed"
    assert stripe_state["retrieved"] == ["sub_1"]
    assert _row(fake_db)["status"] == "trialing"
    assert _row(fake_db)["trial_end"].startswith("2027-01-15")
    assert _row(fake_db)["current_period_end"].startswith("2027-01-15")


def test_period_end_is_read_from_older_api_versions_too(client, production, stripe_state, fake_db):
    stripe_state["subscriptions"]["sub_1"] = subscription("active", current_period_end=1_700_000_000)
    post_event(client, event("customer.subscription.updated", {"id": "sub_1"}))
    assert _row(fake_db)["current_period_end"].startswith("2023-11-14")


def test_subscription_deleted_ends_the_plan_and_cancels_pending_posts(client, production, stripe_state, fake_db, auth_headers):
    make_pro(fake_db)
    fake_db.tables["publish_jobs"] = [
        {"id": "j1", "user_id": "user-a", "status": "scheduled"},
        {"id": "j2", "user_id": "user-a", "status": "published"},
        {"id": "j3", "user_id": "user-b", "status": "scheduled"},
    ]
    fake_db.tables["connected_accounts"] = [{"id": "a1", "user_id": "user-a", "status": "connected"}]
    stripe_state["subscriptions"]["sub_1"] = subscription("canceled")

    post_event(client, event("customer.subscription.deleted", {"id": "sub_1"}))

    assert client.get("/billing/entitlements", headers=auth_headers("user-a")).json()["plan"] == "free"
    jobs = {j["id"]: j for j in fake_db.tables["publish_jobs"]}
    assert (jobs["j1"]["status"], jobs["j1"]["error_code"]) == ("cancelled", "subscription_ended")
    assert jobs["j2"]["status"] == "published"       # history is kept
    assert jobs["j3"]["status"] == "scheduled"       # another user's
    assert fake_db.tables["connected_accounts"][0]["status"] == "connected"  # accounts are kept


def test_payment_failed_pauses_publishing_and_keeps_scheduled_posts(client, production, stripe_state, fake_db, auth_headers):
    make_pro(fake_db)
    fake_db.tables["publish_jobs"] = [{"id": "j1", "user_id": "user-a", "status": "scheduled"}]
    stripe_state["subscriptions"]["sub_1"] = subscription("past_due")

    resp = post_event(client, event("invoice.payment_failed", {"id": "in_1", "subscription": "sub_1"}))

    assert resp.json()["outcome"] == "processed"
    body = client.get("/billing/entitlements", headers=auth_headers("user-a")).json()
    assert (body["plan"], body["can_publish"], body["publishing_paused"]) == ("pro", False, True)
    assert fake_db.tables["publish_jobs"][0]["status"] == "scheduled"  # only cancelled once the grace period ends


def test_invoice_paid_restores_publishing(client, production, stripe_state, fake_db, auth_headers):
    make_pro(fake_db, status="past_due")
    stripe_state["subscriptions"]["sub_1"] = subscription("active")
    # Newer API versions carry the subscription under parent.subscription_details.
    post_event(client, event("invoice.paid", {
        "id": "in_1", "parent": {"subscription_details": {"subscription": "sub_1"}}}))
    assert client.get("/billing/entitlements", headers=auth_headers("user-a")).json()["can_publish"] is True


def test_an_invoice_with_no_subscription_is_ignored(client, production, stripe_state, fake_db):
    resp = post_event(client, event("invoice.paid", {"id": "in_1"}))
    assert resp.json()["outcome"] == "ignored"
    assert stripe_state["retrieved"] == []


def test_other_event_types_are_acknowledged_and_ignored(client, production, stripe_state, fake_db):
    resp = post_event(client, event("customer.created", {"id": "cus_1"}))
    assert resp.status_code == 200 and resp.json()["outcome"] == "ignored"
    assert fake_db.tables.get("stripe_events", []) == []


def test_a_subscription_for_no_known_user_is_acknowledged_and_changes_nothing(client, production, stripe_state, fake_db):
    stripe_state["subscriptions"]["sub_9"] = subscription(user_id=None, sub_id="sub_9", customer="cus_stranger")
    resp = post_event(client, event("customer.subscription.updated", {"id": "sub_9"}))
    assert resp.status_code == 200 and resp.json()["outcome"] == "ignored"
    assert fake_db.tables.get("subscriptions", []) == []


# --- Webhook: idempotency ---------------------------------------------------------

def test_a_redelivered_event_is_applied_once(client, production, stripe_state, fake_db):
    stripe_state["subscriptions"]["sub_1"] = subscription("active")
    evt = event("customer.subscription.updated", {"id": "sub_1"}, event_id="evt_same")

    assert post_event(client, evt).json()["outcome"] == "processed"
    stripe_state["subscriptions"]["sub_1"] = subscription("canceled")  # would change the row if applied again
    assert post_event(client, evt).json()["outcome"] == "duplicate"

    assert stripe_state["retrieved"] == ["sub_1"]
    assert _row(fake_db)["status"] == "active"
    assert [e["event_id"] for e in fake_db.tables["stripe_events"]] == ["evt_same"]


def test_a_failed_event_is_retried_when_stripe_sends_it_again(client, production, stripe_state, fake_db):
    evt = event("customer.subscription.updated", {"id": "sub_1"})
    # Stripe has no such subscription yet, so the fetch fails.
    assert post_event(client, evt).status_code == 500
    assert fake_db.tables.get("stripe_events", []) == []

    stripe_state["subscriptions"]["sub_1"] = subscription("active")
    assert post_event(client, evt).json()["outcome"] == "processed"
    assert _row(fake_db)["status"] == "active"


def test_events_out_of_order_end_in_stripes_current_state(client, production, stripe_state, fake_db):
    stripe_state["subscriptions"]["sub_1"] = subscription("active")
    post_event(client, event("customer.subscription.updated", {"id": "sub_1", "status": "active"}, "evt_2"))
    # The older "created" event arrives late, still saying "trialing".
    post_event(client, event("customer.subscription.created", {"id": "sub_1", "status": "trialing"}, "evt_1"))
    assert _row(fake_db)["status"] == "active"


def test_the_plan_never_changes_from_the_browser(client, a_headers, stripe_state, fake_db):
    """No authenticated endpoint writes a subscription status."""
    client.post("/billing/checkout", headers=a_headers)
    for method, path in [("post", "/billing/portal"), ("get", "/billing/entitlements")]:
        getattr(client, method)(path, headers=a_headers, params={"status": "active", "plan": "pro"})
    assert fake_db.tables["subscriptions"][0].get("status") is None
