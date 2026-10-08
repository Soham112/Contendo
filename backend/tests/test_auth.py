"""Token verification in auth/supabase_jwt.py and how endpoints respond to it."""

import pytest

from tests.conftest import TEST_ADMIN_USER_ID, make_token


# --- get_user_id() directly ----------------------------------------------

def test_valid_token_returns_its_user_id(production):
    from auth.supabase_jwt import get_user_id

    assert get_user_id(f"Bearer {make_token('user-123')}") == "user-123"


@pytest.mark.parametrize("header", [None, "", "Token abc", "Bearer"])
def test_production_rejects_missing_or_malformed_header(production, header):
    from auth.supabase_jwt import get_user_id
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        get_user_id(header)
    assert exc.value.status_code == 401


def test_production_rejects_expired_token(production):
    from auth.supabase_jwt import get_user_id
    from fastapi import HTTPException

    expired = make_token("user-123", expires_in=-60)
    with pytest.raises(HTTPException) as exc:
        get_user_id(f"Bearer {expired}")
    assert exc.value.status_code == 401


def test_production_rejects_token_signed_with_wrong_secret(production):
    from auth.supabase_jwt import get_user_id
    from fastapi import HTTPException

    forged = make_token("user-123", secret="some-other-secret-that-is-32-bytes-long!!")
    with pytest.raises(HTTPException) as exc:
        get_user_id(f"Bearer {forged}")
    assert exc.value.status_code == 401


def test_production_rejects_token_with_wrong_audience(production):
    import time

    import jwt
    from auth.supabase_jwt import get_user_id
    from fastapi import HTTPException
    from tests.conftest import TEST_JWT_SECRET

    token = jwt.encode(
        {"sub": "user-123", "aud": "anon", "exp": int(time.time()) + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        get_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


# --- Fails closed in every environment ------------------------------------

ENVIRONMENTS = [None, "", "development", "staging", "production"]


def _set_environment(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", value)


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_missing_token_is_401_whatever_environment_says(client, monkeypatch, environment):
    _set_environment(monkeypatch, environment)
    assert client.get("/history").status_code == 401


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_invalid_token_is_401_whatever_environment_says(client, monkeypatch, auth_headers, environment):
    _set_environment(monkeypatch, environment)
    forged = auth_headers("user-a", secret="some-other-secret-that-is-32-bytes-long!!")
    assert client.get("/history", headers=forged).status_code == 401
    assert client.get("/history", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_401_body_does_not_carry_the_exception_text(client, auth_headers, caplog):
    expired = auth_headers("user-a", expires_in=-60)
    with caplog.at_level("WARNING", logger="auth.supabase_jwt"):
        resp = client.get("/history", headers=expired)

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}
    assert "expired" not in resp.text.lower()
    # The reason is still available to whoever reads the server log.
    assert "ExpiredSignatureError" in caplog.text


# --- Dev auth: explicit opt-in only -----------------------------------------

def test_dev_auth_lets_missing_and_invalid_tokens_act_as_the_dev_user(dev_auth):
    from auth.supabase_jwt import DEV_USER_ID, get_user_id

    assert get_user_id(None) == DEV_USER_ID
    assert get_user_id("Bearer not-a-jwt") == DEV_USER_ID


def test_dev_auth_still_honours_a_valid_token(dev_auth):
    from auth.supabase_jwt import get_user_id

    assert get_user_id(f"Bearer {make_token('user-123')}") == "user-123"


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "on", "2"])
def test_dev_auth_needs_the_flag_to_be_exactly_1(client, monkeypatch, value):
    monkeypatch.setenv("ALLOW_DEV_AUTH", value)
    assert client.get("/history").status_code == 401


def test_dev_user_is_not_an_admin(client, dev_auth):
    assert client.get("/history").status_code == 200
    assert client.get("/admin/usage").status_code == 403


@pytest.mark.parametrize("environment", ["production", "Production", " production "])
def test_startup_refuses_dev_auth_in_production(monkeypatch, environment):
    from fastapi.testclient import TestClient

    from config.security import SecurityConfigError
    from main import app

    monkeypatch.setenv("ALLOW_DEV_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", environment)

    with pytest.raises(SecurityConfigError, match="ALLOW_DEV_AUTH"):
        with TestClient(app):
            pass


def test_dev_auth_in_production_never_serves_a_request(monkeypatch):
    """Even if the flag appears after startup, verification refuses to run."""
    from auth.supabase_jwt import get_user_id
    from config.security import SecurityConfigError

    monkeypatch.setenv("ALLOW_DEV_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(SecurityConfigError):
        get_user_id(None)


@pytest.mark.parametrize("env,expected", [
    ({}, "AUTH MODE: strict"),
    ({"ENVIRONMENT": "production"}, "AUTH MODE: strict"),
    ({"ALLOW_DEV_AUTH": "1", "ENVIRONMENT": "development"}, "AUTH MODE: dev"),
])
def test_startup_logs_the_auth_mode(monkeypatch, caplog, env, expected):
    from fastapi.testclient import TestClient

    from main import app

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with caplog.at_level("INFO", logger="main"):
        with TestClient(app):
            pass
    assert expected in caplog.text


# --- Through the HTTP layer ------------------------------------------------

def test_protected_endpoint_rejects_expired_token(client, production, auth_headers):
    resp = client.get("/history", headers=auth_headers("user-a", expires_in=-60))
    assert resp.status_code == 401


# --- Admin routes -----------------------------------------------------------

ADMIN_ROUTES = ["/admin/usage", "/admin/analytics-data"]


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_allows_an_allowlisted_user(client, auth_headers, path):
    assert client.get(path, headers=auth_headers(TEST_ADMIN_USER_ID)).status_code == 200
    # The allowlist is comma-separated and tolerates spaces.
    assert client.get(path, headers=auth_headers("another-admin")).status_code == 200


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_refuses_other_users(client, auth_headers, path):
    assert client.get(path, headers=auth_headers("user-a")).status_code == 403


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_requires_a_token(client, auth_headers, path):
    assert client.get(path).status_code == 401
    forged = auth_headers(TEST_ADMIN_USER_ID, secret="some-other-secret-that-is-32-bytes-long!!")
    assert client.get(path, headers=forged).status_code == 401


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_old_admin_secret_header_no_longer_grants_access(client, auth_headers, monkeypatch, path):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    assert client.get(path, headers={"x-admin-secret": "s3cret"}).status_code == 401
    as_user = {**auth_headers("user-a"), "x-admin-secret": "s3cret"}
    assert client.get(path, headers=as_user).status_code == 403


@pytest.mark.parametrize("allowlist", ["", " ", ",", " , "])
@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_empty_allowlist_means_nobody_is_admin(client, auth_headers, monkeypatch, path, allowlist):
    monkeypatch.setenv("ADMIN_USER_IDS", allowlist)
    assert client.get(path, headers=auth_headers(TEST_ADMIN_USER_ID)).status_code == 403
    # A token whose sub is empty must not match an empty allowlist entry.
    assert client.get(path, headers=auth_headers("")).status_code == 403


def test_admin_id_must_match_exactly(client, auth_headers):
    for near_miss in (TEST_ADMIN_USER_ID.upper(), TEST_ADMIN_USER_ID + "x", TEST_ADMIN_USER_ID[:-1]):
        assert client.get("/admin/usage", headers=auth_headers(near_miss)).status_code == 403


def test_admin_me_reports_status_without_granting_anything(client, auth_headers):
    assert client.get("/admin/me", headers=auth_headers(TEST_ADMIN_USER_ID)).json() == {"is_admin": True}
    assert client.get("/admin/me", headers=auth_headers("user-a")).json() == {"is_admin": False}
    assert client.get("/admin/me").status_code == 401
