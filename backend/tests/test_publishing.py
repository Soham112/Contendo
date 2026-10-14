"""The publishing layer on the fake provider: the paywall gate, connecting
accounts, creating and cancelling jobs, the worker (retries, backoff,
idempotency), statuses and the provider webhook."""

from datetime import datetime, timedelta, timezone

import pytest

from publishing.types import AccountStatus, ErrorCode, JobStatus, Platform, ProviderError, PublishStatus, AccountResult


@pytest.fixture
def provider(monkeypatch):
    from publishing.fake import fake_provider

    monkeypatch.setenv("PUBLISHING_PROVIDER", "fake")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example")
    fake_provider.reset()
    return fake_provider


@pytest.fixture
def a_headers(client, auth_headers, provider):
    return auth_headers("user-a")


@pytest.fixture
def pro(fake_db):
    def make(user_id="user-a", status="active"):
        fake_db.tables.setdefault("subscriptions", []).append({"user_id": user_id, "status": status})
    make()
    return make


def connect(client, headers, platform="linkedin") -> dict:
    """Connect one account through the API; returns its row as the API lists it."""
    url = client.post("/publishing/connect", headers=headers, json={"platform": platform}).json()["url"]
    assert "connect_status=success" in url
    return client.get("/publishing/accounts", headers=headers).json()["accounts"][-1]


def publish(client, headers, account_ids, **overrides):
    body = {"content": "We are open on Sundays now.", "account_ids": account_ids, "when": "now", **overrides}
    if body["content"].strip():
        checked = client.post("/publishing/reviews", headers=headers, json={
            "content": body["content"], "post_id": body.get("post_id"), "media": body.get("media", []),
        })
        if checked.status_code == 200:
            review = checked.json()
            approved = client.post(f"/publishing/reviews/{review['id']}/approve", headers=headers, json={
                "content": body["content"], "accepted_flag_ids": [flag["id"] for flag in review["flags"]],
            })
            assert approved.status_code == 200
            body["approval_id"] = review["id"]
    return client.post("/publishing/jobs", headers=headers, json=body)


def job_row(fake_db, index=0) -> dict:
    return fake_db.tables["publish_jobs"][index]


def tick() -> int:
    from publishing.worker import run_once
    return run_once()


def make_due(fake_db) -> None:
    """Bring every waiting job forward to now (as if its backoff had passed)."""
    for row in fake_db.tables["publish_jobs"]:
        row["next_attempt_at"] = datetime.now(timezone.utc).isoformat()


# --- Provider interface ---------------------------------------------------------

def test_the_fake_satisfies_the_provider_interface(provider):
    from publishing.provider import PublishingProvider, get_provider

    assert get_provider() is provider
    for method in ("create_end_user", "get_connect_url", "list_connected_accounts", "disconnect_account",
                   "upload_media", "publish", "get_status", "cancel", "parse_webhook"):
        assert callable(getattr(provider, method)), method
        assert hasattr(PublishingProvider, method)


def test_an_unknown_or_missing_provider_is_a_config_error(monkeypatch):
    from publishing.provider import PublishingConfigError, get_provider

    for value in ("", "postiz"):
        monkeypatch.setenv("PUBLISHING_PROVIDER", value)
        with pytest.raises(PublishingConfigError):
            get_provider()


def test_the_fake_provider_refuses_to_run_in_production(monkeypatch):
    from publishing.provider import PublishingConfigError, get_provider

    monkeypatch.setenv("PUBLISHING_PROVIDER", "fake")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(PublishingConfigError):
        get_provider()


def test_zernio_needs_its_settings(monkeypatch):
    from publishing.provider import PublishingConfigError, get_provider

    monkeypatch.setenv("PUBLISHING_PROVIDER", "zernio")
    with pytest.raises(PublishingConfigError):
        get_provider()


def test_publishing_endpoints_are_503_without_a_provider(client, auth_headers, pro):
    assert client.get("/publishing/accounts", headers=auth_headers("user-a")).status_code == 503


# --- Paywall gate ---------------------------------------------------------------

def test_a_free_user_cannot_connect_or_publish(client, a_headers, fake_db):
    for resp in (
        client.post("/publishing/connect", headers=a_headers, json={"platform": "instagram"}),
        publish(client, a_headers, ["anything"]),
    ):
        assert resp.status_code == 402
        detail = resp.json()["detail"]
        assert detail["code"] == "upgrade_required"
        assert detail["entitlements"]["plan"] == "free"
    assert fake_db.tables.get("publish_jobs", []) == []
    assert fake_db.tables.get("connected_accounts", []) == []


def test_a_free_user_can_still_see_and_disconnect(client, a_headers, fake_db, pro):
    account = connect(client, a_headers)
    fake_db.tables["subscriptions"][0]["status"] = "canceled"

    assert client.get("/publishing/accounts", headers=a_headers).json()["accounts"][0]["id"] == account["id"]
    assert client.get("/publishing/jobs", headers=a_headers).status_code == 200
    assert client.delete(f"/publishing/accounts/{account['id']}", headers=a_headers).status_code == 200


def test_a_past_due_user_is_told_publishing_is_paused(client, a_headers, fake_db, pro):
    account = connect(client, a_headers)
    fake_db.tables["subscriptions"][0]["status"] = "past_due"
    resp = publish(client, a_headers, [account["id"]])
    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "payment_required"


def test_the_account_limit_is_one_per_platform(client, a_headers, pro):
    connect(client, a_headers, "linkedin")
    resp = client.post("/publishing/connect", headers=a_headers, json={"platform": "linkedin"})
    assert resp.status_code == 402
    assert "Disconnect one" in resp.json()["detail"]["message"]
    assert client.post("/publishing/connect", headers=a_headers, json={"platform": "facebook"}).status_code == 200


def test_publishing_endpoints_require_a_token(client, provider):
    assert client.get("/publishing/accounts").status_code == 401
    assert client.post("/publishing/jobs", json={}).status_code == 401
    assert client.post("/publishing/jobs/x/cancel").status_code == 401


# --- Connected accounts ---------------------------------------------------------

def test_connecting_creates_one_tenant_and_lists_the_account(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers, "instagram")
    connect(client, a_headers, "facebook")

    assert account["platform"] == "instagram" and account["label"] == "Instagram"
    assert account["status"] == "connected"
    assert list(provider.users) == ["user-a"]  # one tenant, created once
    assert fake_db.tables["accounts"][0]["publishing_ref"] == "fake-user-user-a"
    # Only the provider's reference is stored: no token, no password.
    assert set(fake_db.tables["connected_accounts"][0]) <= {
        "id", "user_id", "provider", "provider_account_ref", "platform", "display_name", "status", "updated_at"}


def test_an_unknown_platform_is_rejected(client, a_headers, pro):
    assert client.post("/publishing/connect", headers=a_headers, json={"platform": "myspace"}).status_code == 422


def test_an_account_the_provider_reports_expired_needs_reconnecting(client, a_headers, pro, provider):
    account = connect(client, a_headers, "instagram")
    ref = next(iter(provider.accounts["fake-user-user-a"]))
    provider.set_account_status("fake-user-user-a", ref, AccountStatus.NEEDS_RECONNECT)

    listed = client.get("/publishing/accounts", headers=a_headers).json()["accounts"]
    assert listed[0]["status"] == "needs_reconnect"
    resp = publish(client, a_headers, [account["id"]], media=[{"ref": "m", "kind": "image"}])
    assert resp.json()["detail"]["problems"] == ["Reconnect Instagram before publishing to it."]


def test_disconnecting_removes_it_at_the_provider_and_from_the_list(client, a_headers, pro, provider):
    account = connect(client, a_headers)
    assert client.delete(f"/publishing/accounts/{account['id']}", headers=a_headers).status_code == 200
    assert provider.accounts["fake-user-user-a"] == {}
    assert client.get("/publishing/accounts", headers=a_headers).json()["accounts"] == []


def test_accounts_are_isolated_between_users(client, a_headers, auth_headers, pro):
    account = connect(client, a_headers)
    pro("user-b")
    b_headers = auth_headers("user-b")

    assert client.get("/publishing/accounts", headers=b_headers).json()["accounts"] == []
    assert client.delete(f"/publishing/accounts/{account['id']}", headers=b_headers).status_code == 404
    resp = publish(client, b_headers, [account["id"]])
    assert resp.status_code == 422 and "no longer connected" in resp.json()["detail"]["problems"][0]


# --- Creating jobs: validation on the server ------------------------------------

def test_publish_now_only_queues_the_job(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    resp = publish(client, a_headers, [account["id"]])

    assert resp.status_code == 200
    assert resp.json()["job"]["status"] == "scheduled"
    assert provider.publish_calls == []  # nothing is sent inside the request
    assert job_row(fake_db)["scheduled_at"] is None


@pytest.mark.parametrize("platform, content, media, problem", [
    ("x", "x" * 281, [], "X allows 280 characters and this post has 281."),
    ("linkedin", "x" * 3001, [], "LinkedIn allows 3,000 characters"),
    ("instagram", "Hello", [], "Instagram posts need an image or a video."),
    ("tiktok", "Hello", [{"ref": "m", "kind": "image"}], "TikTok posts need a video."),
    ("youtube", "Hello", [], "YouTube posts need a video."),
    ("google_business", "Hello", [{"ref": "a", "kind": "image"}, {"ref": "b", "kind": "image"}],
     "Google Business Profile allows 1 image per post."),
])
def test_a_post_a_platform_would_refuse_is_rejected_before_it_is_queued(
        client, a_headers, pro, fake_db, platform, content, media, problem):
    account = connect(client, a_headers, platform)
    resp = publish(client, a_headers, [account["id"]], content=content, media=media)

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "cannot_publish"
    assert any(problem in p for p in resp.json()["detail"]["problems"])
    assert fake_db.tables.get("publish_jobs", []) == []


@pytest.mark.parametrize("platform, content, media", [
    ("x", "x" * 280, []),
    ("instagram", "Hello", [{"ref": "m", "kind": "image"}]),
    ("tiktok", "Hello", [{"ref": "m", "kind": "video"}]),
    ("facebook", "Hello", []),
])
def test_a_post_within_the_rules_is_accepted(client, a_headers, pro, platform, content, media):
    account = connect(client, a_headers, platform)
    assert publish(client, a_headers, [account["id"]], content=content, media=media).status_code == 200


def test_empty_content_and_no_accounts_are_rejected(client, a_headers, pro):
    resp = publish(client, a_headers, [], content="  ")
    assert resp.status_code == 422
    assert len(resp.json()["detail"]["problems"]) == 2


def test_a_job_for_someone_elses_post_is_refused(client, a_headers, pro, fake_db):
    account = connect(client, a_headers)
    fake_db.tables["posts"] = [{"id": 7, "user_id": "user-b", "content": "theirs"}]
    assert publish(client, a_headers, [account["id"]], post_id=7).status_code == 404


def test_schedule_needs_a_future_time_with_an_offset(client, a_headers, pro, fake_db):
    account = connect(client, a_headers)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert publish(client, a_headers, [account["id"]], when="schedule", scheduled_at=past).status_code == 422
    assert publish(client, a_headers, [account["id"]], when="schedule").status_code == 422
    assert publish(client, a_headers, [account["id"]], when="schedule",
                   scheduled_at="2030-01-01T09:00:00").status_code == 422  # no offset: whose 9am?

    resp = publish(client, a_headers, [account["id"]], when="schedule", scheduled_at="2030-01-01T09:00:00-05:00")
    assert resp.status_code == 200
    assert job_row(fake_db)["scheduled_at"] == "2030-01-01T14:00:00+00:00"
    assert tick() == 0  # not due


def test_the_queue_gives_each_post_the_next_free_morning_in_the_users_zone(client, a_headers, pro, fake_db):
    account = connect(client, a_headers)
    for _ in range(3):
        assert publish(client, a_headers, [account["id"]], when="queue", timezone="America/New_York").status_code == 200

    from zoneinfo import ZoneInfo
    slots = [datetime.fromisoformat(r["scheduled_at"]).astimezone(ZoneInfo("America/New_York"))
             for r in fake_db.tables["publish_jobs"]]
    assert all((slot.hour, slot.minute) == (9, 0) for slot in slots)
    assert slots[0] > datetime.now(timezone.utc)
    assert [(b.date() - a.date()).days for a, b in zip(slots, slots[1:])] == [1, 1]


def test_the_queue_fills_the_first_free_day_whatever_else_is_waiting(client, a_headers, pro, fake_db):
    from zoneinfo import ZoneInfo
    from publishing.service import next_queue_slot

    tz = ZoneInfo("America/New_York")
    now = datetime(2026, 10, 13, 15, 0, tzinfo=tz)  # 3pm: today's 9am has passed
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])  # waiting to go out now: holds no day
    publish(client, a_headers, [account["id"]], when="schedule", scheduled_at="2030-06-03T09:30:00-04:00")
    assert next_queue_slot("user-a", tz, now) == datetime(2026, 10, 14, 9, 0, tzinfo=tz)

    # Tomorrow taken: the day after. A cancelled post frees its day again.
    fake_db.tables["publish_jobs"].append({"id": "x", "user_id": "user-a", "status": "scheduled",
                                           "scheduled_at": "2026-10-14T20:00:00+00:00"})
    assert next_queue_slot("user-a", tz, now) == datetime(2026, 10, 15, 9, 0, tzinfo=tz)
    fake_db.tables["publish_jobs"][-1]["status"] = "cancelled"
    assert next_queue_slot("user-a", tz, now) == datetime(2026, 10, 14, 9, 0, tzinfo=tz)

    # Before 9am, today's slot is still open; another user's posts never count.
    early = datetime(2026, 10, 13, 7, 0, tzinfo=tz)
    assert next_queue_slot("user-a", tz, early) == datetime(2026, 10, 13, 9, 0, tzinfo=tz)
    assert next_queue_slot("user-b", tz, now) == datetime(2026, 10, 14, 9, 0, tzinfo=tz)


def test_an_unknown_time_zone_is_rejected(client, a_headers, pro):
    account = connect(client, a_headers)
    assert publish(client, a_headers, [account["id"]], when="queue", timezone="Mars/Olympus").status_code == 422


# --- The worker -----------------------------------------------------------------

def test_the_worker_publishes_a_due_job_and_marks_the_post_published(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    fake_db.tables["posts"] = [{"id": 7, "user_id": "user-a", "content": "Draft"}]
    publish(client, a_headers, [account["id"]], post_id=7)

    assert tick() == 1

    job = client.get("/publishing/jobs", headers=a_headers).json()["jobs"][0]
    assert job["status"] == "published" and job["published_at"]
    assert job["results"][0]["status"] == "published"
    assert job["results"][0]["url"].startswith("https://")
    assert job["message"] == ""
    assert fake_db.tables["posts"][0]["published_platform"] == "LinkedIn"
    assert len(provider.publish_calls) == 1
    assert tick() == 0  # nothing left to do


def test_a_transient_failure_is_retried_with_exponential_backoff(client, a_headers, pro, provider, fake_db):
    from publishing.jobs import backoff

    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    for _ in range(2):
        provider.fail_next_publish(ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, "503", retryable=True))

    waits = []
    for attempt in (1, 2):
        before = datetime.now(timezone.utc)
        tick()
        row = job_row(fake_db)
        assert (row["status"], row["attempts"]) == ("scheduled", attempt)
        waits.append(datetime.fromisoformat(row["next_attempt_at"]) - before)
        assert tick() == 0  # waiting, not hammering
        make_due(fake_db)

    assert timedelta(seconds=59) < waits[0] < timedelta(seconds=62)
    assert timedelta(seconds=119) < waits[1] < timedelta(seconds=122)
    assert [backoff(n).total_seconds() for n in (1, 2, 3, 4)] == [60, 120, 240, 480]

    tick()
    assert job_row(fake_db)["status"] == "published"
    assert job_row(fake_db)["error_code"] is None


def test_every_attempt_sends_the_same_idempotency_key(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    provider.fail_next_publish(ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, retryable=True))
    tick()
    make_due(fake_db)
    tick()

    keys = {call["idempotency_key"] for call in provider.publish_calls}
    assert len(provider.publish_calls) == 2 and len(keys) == 1
    assert keys == {job_row(fake_db)["idempotency_key"]}


def test_a_job_interrupted_after_the_provider_accepted_it_does_not_post_twice(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    tick()
    assert len(provider.publishes) == 1
    # As if the process had died before recording the provider's answer.
    row = job_row(fake_db)
    row.update(status="publishing", provider_post_ref=None,
               locked_at=(datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat())

    assert tick() == 1  # claimed again as stale
    assert len(provider.publishes) == 1  # the provider saw the same key: no second post
    assert job_row(fake_db)["status"] == "published"


def test_a_fresh_claim_is_not_taken_by_a_second_worker(client, a_headers, pro, fake_db):
    from memory.publish_store import claim_due_jobs

    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    assert len(claim_due_jobs(5)) == 1
    assert claim_due_jobs(5) == []


def test_retries_stop_after_the_last_attempt(client, a_headers, pro, provider, fake_db):
    from publishing.jobs import MAX_ATTEMPTS

    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    for _ in range(MAX_ATTEMPTS):
        provider.fail_next_publish(ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, "raw provider text", retryable=True))
        make_due(fake_db)
        tick()

    job = client.get("/publishing/jobs", headers=a_headers).json()["jobs"][0]
    assert job["status"] == "failed" and job_row(fake_db)["attempts"] == MAX_ATTEMPTS
    assert "Nothing was posted" in job["message"]
    assert "raw provider text" not in str(job)  # the provider's own words never reach the user
    assert tick() == 0


def test_a_permanent_failure_is_not_retried_and_says_what_to_do(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    provider.fail_next_publish(ProviderError(ErrorCode.CONTENT_REJECTED, "policy 368"))
    tick()

    job = client.get("/publishing/jobs", headers=a_headers).json()["jobs"][0]
    assert (job["status"], job_row(fake_db)["attempts"]) == ("failed", 1)
    assert job["message"] == "Your account didn't accept this post. Edit it and try again."


def test_an_expired_connection_fails_with_a_reconnect_message(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers, "facebook")
    publish(client, a_headers, [account["id"]])
    ref = fake_db.tables["connected_accounts"][0]["provider_account_ref"]

    def reject(provider_user_ref, post, account_refs, schedule_at, *, idempotency_key):
        provider.publishes["p1"] = {"status": PublishStatus(JobStatus.FAILED, (AccountResult(
            ref, JobStatus.FAILED, error_code=ErrorCode.RECONNECT_REQUIRED, error_message="OAuthException 190"),))}
        return "p1"

    provider.publish = reject
    try:
        tick()
    finally:
        del provider.publish

    job = client.get("/publishing/jobs", headers=a_headers).json()["jobs"][0]
    assert job["status"] == "failed"
    assert job["message"] == "Reconnect Facebook, then publish this post again."
    assert "OAuthException" not in str(job)
    assert fake_db.tables["connected_accounts"][0]["status"] == "needs_reconnect"


def test_a_job_whose_account_was_disconnected_fails_clearly(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]], when="schedule",
            scheduled_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    client.delete(f"/publishing/accounts/{account['id']}", headers=a_headers)
    make_due(fake_db)
    tick()

    assert job_row(fake_db)["error_code"] == "account_removed"
    assert provider.publish_calls == []


def test_one_broken_job_does_not_stop_the_others(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    publish(client, a_headers, [account["id"]], content="Second post.")
    provider.fail_next_publish(RuntimeError("bug"))  # not a ProviderError
    tick()
    assert sorted(r["status"] for r in fake_db.tables["publish_jobs"]) == ["published", "publishing"]


# --- When the plan lapses -------------------------------------------------------

def test_a_job_due_while_payment_is_failing_waits_without_using_an_attempt(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    publish(client, a_headers, [account["id"]])
    fake_db.tables["subscriptions"][0]["status"] = "past_due"
    tick()

    row = job_row(fake_db)
    assert (row["status"], row["attempts"], row["error_code"]) == ("scheduled", 0, "payment_required")
    assert provider.publish_calls == []
    job = client.get("/publishing/jobs", headers=a_headers).json()["jobs"][0]
    assert "Update your payment method" in job["message"]

    fake_db.tables["subscriptions"][0]["status"] = "active"
    make_due(fake_db)
    tick()
    assert job_row(fake_db)["status"] == "published"


# --- Cancelling -----------------------------------------------------------------

def test_a_scheduled_job_can_be_cancelled_and_is_never_sent(client, a_headers, pro, provider, fake_db):
    account = connect(client, a_headers)
    job_id = publish(client, a_headers, [account["id"]]).json()["job"]["id"]

    resp = client.post(f"/publishing/jobs/{job_id}/cancel", headers=a_headers)
    assert resp.json()["job"]["status"] == "cancelled"
    assert tick() == 0 and provider.publish_calls == []


def test_a_published_job_cannot_be_cancelled(client, a_headers, pro, fake_db):
    account = connect(client, a_headers)
    job_id = publish(client, a_headers, [account["id"]]).json()["job"]["id"]
    tick()
    assert client.post(f"/publishing/jobs/{job_id}/cancel", headers=a_headers).status_code == 409
    assert job_row(fake_db)["status"] == "published"


def test_another_users_job_cannot_be_seen_or_cancelled(client, a_headers, auth_headers, pro, fake_db):
    account = connect(client, a_headers)
    job_id = publish(client, a_headers, [account["id"]]).json()["job"]["id"]
    b_headers = auth_headers("user-b")

    assert client.get("/publishing/jobs", headers=b_headers).json()["jobs"] == []
    assert client.post(f"/publishing/jobs/{job_id}/cancel", headers=b_headers).status_code == 404
    assert job_row(fake_db)["status"] == "scheduled"


# --- Status from the provider ---------------------------------------------------

def _accepted_job(client, headers, provider, fake_db) -> dict:
    """A job the provider has accepted but not yet confirmed."""
    account = connect(client, headers)
    publish(client, headers, [account["id"]])
    tick()
    row = job_row(fake_db)
    row["status"] = "publishing"
    provider.set_status(row["provider_post_ref"], PublishStatus(JobStatus.PUBLISHING))
    return row


def test_the_webhook_needs_a_valid_signature(client, a_headers, pro, provider, fake_db):
    row = _accepted_job(client, a_headers, provider, fake_db)
    body = {"provider_post_ref": row["provider_post_ref"], "status": "published"}

    assert client.post("/publishing/webhook", json=body).status_code == 400
    assert client.post("/publishing/webhook", json=body, headers={"x-fake-signature": "nope"}).status_code == 400
    assert row["status"] == "publishing"

    resp = client.post("/publishing/webhook", json=body, headers={"x-fake-signature": "valid"})
    assert resp.json() == {"received": True, "outcome": "applied"}
    assert job_row(fake_db)["status"] == "published"


def test_a_webhook_for_an_unknown_post_changes_nothing(client, a_headers, pro, provider, fake_db):
    resp = client.post("/publishing/webhook", json={"provider_post_ref": "nope", "status": "failed"},
                       headers={"x-fake-signature": "valid"})
    assert resp.json()["outcome"] == "unknown_post"


def test_a_job_with_no_webhook_is_confirmed_by_asking_the_provider(client, a_headers, pro, provider, fake_db):
    row = _accepted_job(client, a_headers, provider, fake_db)
    row["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    provider.set_status(row["provider_post_ref"], PublishStatus(JobStatus.PUBLISHED))

    tick()
    assert job_row(fake_db)["status"] == "published"


# --- Zernio adapter: mapping only (no network) -----------------------------------

def _zernio(handler):
    import httpx
    from publishing.zernio import BASE_URL, ZernioProvider

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return ZernioProvider("key", "whsec", client=client)


def test_zernio_maps_accounts_and_skips_platforms_we_do_not_publish_to():
    import httpx

    zernio = _zernio(lambda request: httpx.Response(200, json={"accounts": [
        {"_id": "a1", "platform": "googlebusiness", "displayName": "Harbor Realty", "isActive": True},
        {"_id": "a2", "platform": "twitter", "username": "@harbor", "isActive": True, "needsReconnection": True},
        {"_id": "a3", "platform": "pinterest", "isActive": True},
    ]}))
    accounts = zernio.list_connected_accounts("profile-1")
    assert [(a.ref, a.platform, a.display_name, a.status) for a in accounts] == [
        ("a1", Platform.GOOGLE_BUSINESS, "Harbor Realty", AccountStatus.CONNECTED),
        ("a2", Platform.X, "@harbor", AccountStatus.NEEDS_RECONNECT),
    ]


def test_zernio_reuses_the_profile_it_already_has_for_a_user():
    import httpx
    from publishing.types import EndUser

    zernio = _zernio(lambda request: httpx.Response(409, json={
        "code": "profile_external_id_conflict", "details": {"existingProfileId": "profile-9"}}))
    assert zernio.create_end_user(EndUser("user-a")) == "profile-9"


def test_zernio_publish_sends_the_idempotency_key_and_our_platform_slugs():
    import httpx, json

    sent = {}

    def handler(request):
        if request.url.path.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [{"_id": "a1", "platform": "twitter", "isActive": True}]})
        sent["key"] = request.headers["Idempotency-Key"]
        sent["body"] = json.loads(request.content)
        return httpx.Response(201, json={"post": {"_id": "post-1", "status": "publishing"}})

    from publishing.types import PostContent
    ref = _zernio(handler).publish("profile-1", PostContent("Hello"), ["a1"], None, idempotency_key="key-1")
    assert ref == "post-1" and sent["key"] == "key-1"
    assert sent["body"] == {"content": "Hello", "platforms": [{"platform": "twitter", "accountId": "a1"}],
                            "publishNow": True}


@pytest.mark.parametrize("status, retryable, code", [
    (429, True, ErrorCode.PROVIDER_UNAVAILABLE), (503, True, ErrorCode.PROVIDER_UNAVAILABLE),
    (400, False, ErrorCode.UNKNOWN),
])
def test_zernio_http_errors_say_whether_to_retry(status, retryable, code):
    import httpx

    with pytest.raises(ProviderError) as raised:
        _zernio(lambda request: httpx.Response(status, json={"error": "x"})).get_status("post-1")
    assert (raised.value.retryable, raised.value.code) == (retryable, code)


def test_zernio_webhook_verifies_the_signature_and_maps_a_partial_failure():
    import hashlib, hmac, json

    body = json.dumps({"event": "post.partial", "id": "evt_1", "post": {
        "id": "post-1", "status": "partial", "platforms": [
            {"platform": "facebook", "status": "published", "accountId": "a1", "publishedUrl": "https://fb.example/1"},
            {"platform": "instagram", "status": "failed", "accountId": "a2", "errorCategory": "auth_expired",
             "error": "token expired"},
        ]}}).encode()
    signature = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    zernio = _zernio(lambda request: None)

    update = zernio.parse_webhook(body, {"x-zernio-signature": signature})
    assert update.provider_post_ref == "post-1"
    assert update.status.status == JobStatus.FAILED
    assert [(a.account_ref, a.status, a.error_code) for a in update.status.accounts] == [
        ("a1", JobStatus.PUBLISHED, None), ("a2", JobStatus.FAILED, ErrorCode.RECONNECT_REQUIRED)]

    with pytest.raises(PermissionError):
        zernio.parse_webhook(body, {"x-zernio-signature": "0" * 64})
    with pytest.raises(PermissionError):
        zernio.parse_webhook(body, {})

    other = json.dumps({"event": "account.connected"}).encode()
    assert zernio.parse_webhook(other, {"x-zernio-signature": hmac.new(b"whsec", other, hashlib.sha256).hexdigest()}) is None
