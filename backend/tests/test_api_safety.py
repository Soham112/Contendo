"""Production-safety behaviour: auth on LLM routes, no event-loop blocking,
usage logging from worker threads, JWKS caching, generic 500s, and CORS."""

import threading
import time

import httpx
import jwt
import pytest
from anthropic import InternalServerError
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm


# --- Auth on routes that had none ---------------------------------------------

NEWLY_PROTECTED = [
    ("/refine", {"json": {"current_draft": "d", "refinement_instruction": "i"}}),
    ("/score", {"json": {"post_content": "p"}}),
    ("/generate-visuals", {"json": {"post_content": "p"}}),
    ("/obsidian/preview", {"json": {"vault_path": "/tmp"}}),
    ("/obsidian/preview-zip", {"files": {"file": ("v.zip", b"PK", "application/zip")}}),
]


@pytest.mark.parametrize("path,kwargs", NEWLY_PROTECTED, ids=[p for p, _ in NEWLY_PROTECTED])
def test_newly_protected_routes_reject_missing_token_in_production(client, production, path, kwargs):
    # No Claude response queued: a 401 must happen before any Claude call.
    resp = client.post(path, **kwargs)
    assert resp.status_code == 401


def test_score_accepts_valid_token(client, production, claude, auth_headers, monkeypatch):
    import routers.generate as generate

    monkeypatch.setattr(generate, "score_text", lambda text: (80, ["ok"]))
    resp = client.post("/score", json={"post_content": "p"}, headers=auth_headers("user-a"))
    assert resp.status_code == 200
    assert resp.json() == {"score": 80, "score_feedback": ["ok"]}


# --- Slow sync work doesn't block the event loop ------------------------------

def test_health_responds_while_generate_is_running(client, monkeypatch):
    import routers.generate as generate

    entered = threading.Event()
    release = threading.Event()

    def slow_pipeline(**kwargs):
        entered.set()
        release.wait(timeout=10)
        return {"post": "p", "score": 1, "score_feedback": [], "iterations": 1}

    monkeypatch.setattr(generate, "run_pipeline", slow_pipeline)

    result = {}
    worker = threading.Thread(
        target=lambda: result.update(resp=client.post(
            "/generate", json={"topic": "t", "format": "linkedin post", "tone": "casual"}
        ))
    )
    worker.start()
    try:
        assert entered.wait(timeout=5), "/generate never reached run_pipeline"
        start = time.monotonic()
        health = client.get("/health")
        elapsed = time.monotonic() - start
        assert health.status_code == 200
        assert elapsed < 2, f"/health took {elapsed:.1f}s while /generate was running"
    finally:
        release.set()
        worker.join(timeout=10)
    assert result["resp"].status_code == 200


# --- Usage logging from worker threads ----------------------------------------

@pytest.fixture
def recorded_usage(monkeypatch):
    import memory.usage_store as usage_store

    recorded: list[dict] = []

    async def fake_insert(payload):
        recorded.append(payload)

    monkeypatch.setattr(usage_store, "_insert_event", fake_insert)
    return recorded


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_agent_usage_is_logged_when_run_in_threadpool(client, claude, recorded_usage):
    from starlette.concurrency import run_in_threadpool

    from agents.humanizer_agent import humanizer_node

    claude.queue("humanized draft")
    state = {
        "user_id": "user-a",
        "profile": {},
        "current_draft": "draft",
        "critic_brief": {},
        "format": "linkedin post",
        "length": "standard",
        "quality": "standard",
    }

    # Runs on the app's event loop, with the agent in a worker thread, the same
    # way the /generate route runs run_pipeline.
    out = client.portal.call(run_in_threadpool, humanizer_node, state)

    assert out["current_draft"] == "humanized draft"
    assert _wait_for(lambda: len(recorded_usage) == 1), "usage event was not logged"
    assert recorded_usage[0]["user_id"] == "user-a"
    assert recorded_usage[0]["event_type"] == "humanize"


def test_usage_is_logged_from_plain_thread_once_loop_is_captured(client, recorded_usage):
    from memory.usage_store import schedule_usage_event

    t = threading.Thread(target=lambda: schedule_usage_event(
        user_id="user-b", event_type="ideation", input_tokens=10, output_tokens=5,
    ))
    t.start()
    t.join()

    assert _wait_for(lambda: len(recorded_usage) == 1)
    assert recorded_usage[0]["user_id"] == "user-b"


def test_schedule_usage_event_without_any_loop_is_a_silent_no_op(recorded_usage):
    from memory.usage_store import schedule_usage_event, set_main_loop

    set_main_loop(None)
    schedule_usage_event(user_id="u", event_type="x", input_tokens=1, output_tokens=1)
    assert recorded_usage == []


# --- JWKS caching -------------------------------------------------------------

@pytest.fixture
def es256(monkeypatch):
    """Point auth at a fake JWKS endpoint; returns helpers to sign tokens and rotate keys."""
    import auth.clerk as clerk

    monkeypatch.setattr(clerk, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(clerk, "SUPABASE_JWT_SECRET", "")
    clerk._clear_jwks_cache()

    keys: dict[str, ec.EllipticCurvePrivateKey] = {}
    published: list[str] = []
    fetches = {"count": 0}

    def add_key(kid: str, publish: bool = True):
        keys[kid] = ec.generate_private_key(ec.SECP256R1())
        if publish:
            published.append(kid)

    def publish(kid: str):
        published.append(kid)

    def fake_fetch():
        fetches["count"] += 1
        jwks = []
        for kid in published:
            jwk = ECAlgorithm.to_jwk(keys[kid].public_key(), as_dict=True)
            jwk["kid"] = kid
            jwks.append(jwk)
        return {"keys": jwks}

    monkeypatch.setattr(clerk, "_fetch_jwks", fake_fetch)

    def token(user_id: str, kid: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600},
            keys[kid], algorithm="ES256", headers={"kid": kid},
        )

    class Helpers:
        pass

    h = Helpers()
    h.add_key, h.publish, h.token, h.fetches, h.clerk = add_key, publish, token, fetches, clerk
    yield h
    clerk._clear_jwks_cache()


def test_jwks_is_fetched_once_across_requests(production, es256):
    es256.add_key("k1")
    for _ in range(3):
        assert es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'k1')}") == "user-a"
    assert es256.fetches["count"] == 1


def test_jwks_is_refetched_after_ttl(production, es256):
    es256.add_key("k1")
    es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'k1')}")
    es256.clerk._jwks_fetched_at -= es256.clerk._JWKS_TTL_SECONDS + 1

    es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'k1')}")
    assert es256.fetches["count"] == 2


def test_unknown_kid_refetches_once_to_pick_up_rotated_key(production, es256):
    es256.add_key("k1")
    es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'k1')}")
    # Age the cache past the cooldown, then rotate: k2 exists only upstream.
    es256.clerk._jwks_fetched_at -= es256.clerk._JWKS_REFETCH_COOLDOWN_SECONDS + 1
    es256.add_key("k2")

    assert es256.clerk.get_user_id(f"Bearer {es256.token('user-b', 'k2')}") == "user-b"
    assert es256.fetches["count"] == 2


def test_unknown_kid_fails_after_one_refetch(production, es256):
    from fastapi import HTTPException

    es256.add_key("k1")
    es256.add_key("rogue", publish=False)

    with pytest.raises(HTTPException) as exc:
        es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'rogue')}")
    assert exc.value.status_code == 401
    # Initial fetch; the forced refetch is skipped because the cache is brand new.
    assert es256.fetches["count"] == 1


def test_repeated_unknown_kids_do_not_refetch_within_cooldown(production, es256):
    from fastapi import HTTPException

    es256.add_key("k1")
    es256.add_key("rogue", publish=False)
    es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'k1')}")
    es256.clerk._jwks_fetched_at -= es256.clerk._JWKS_REFETCH_COOLDOWN_SECONDS + 1

    for _ in range(5):
        with pytest.raises(HTTPException):
            es256.clerk.get_user_id(f"Bearer {es256.token('user-a', 'rogue')}")
    # One forced refetch for the first miss; the next four hit the cooldown.
    assert es256.fetches["count"] == 2


def test_hs256_tokens_never_fetch_jwks(production, es256, monkeypatch, auth_headers):
    from tests.conftest import TEST_JWT_SECRET

    monkeypatch.setattr(es256.clerk, "SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    header = auth_headers("user-a")["Authorization"]
    assert es256.clerk.get_user_id(header) == "user-a"
    assert es256.fetches["count"] == 0


# --- Error leakage ------------------------------------------------------------

def test_500_returns_generic_message_not_exception_text(client, monkeypatch, caplog):
    import routers.generate as generate

    def boom(text):
        raise RuntimeError("secret internal detail: /srv/app/key.pem")

    monkeypatch.setattr(generate, "score_text", boom)
    with caplog.at_level("ERROR"):
        resp = client.post("/score", json={"post_content": "p"})

    assert resp.status_code == 500
    assert "secret internal detail" not in resp.text
    assert "secret internal detail" in caplog.text  # logged with traceback


def test_overloaded_anthropic_error_keeps_503_message(client, monkeypatch):
    import routers.generate as generate

    def overloaded(text):
        response = httpx.Response(529, request=httpx.Request("POST", "https://api.anthropic.com"))
        raise InternalServerError("Overloaded", response=response, body=None)

    monkeypatch.setattr(generate, "score_text", overloaded)
    resp = client.post("/score", json={"post_content": "p"})

    assert resp.status_code == 503
    assert "overloaded" in resp.json()["detail"].lower()


def test_4xx_validation_messages_are_unchanged(client):
    resp = client.post("/score", json={"post_content": "  "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "post_content is required"


# --- CORS ---------------------------------------------------------------------

def _preflight(client, origin):
    return client.options(
        "/generate",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


@pytest.mark.parametrize("origin", [
    "http://localhost:3000",
    "https://contendo-six.vercel.app",
    "https://contendo-git-feature-soham.vercel.app",
])
def test_cors_allows_localhost_and_vercel_origins(client, origin):
    resp = _preflight(client, origin)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", [
    "https://evil.com",
    "https://contendo.vercel.app.evil.com",
    "http://contendo.vercel.app",
])
def test_cors_rejects_other_origins(client, origin):
    resp = _preflight(client, origin)
    assert resp.headers.get("access-control-allow-origin") != origin
