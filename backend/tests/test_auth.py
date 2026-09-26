"""Token verification in auth/supabase_jwt.py and how endpoints respond to it."""

import pytest

from tests.conftest import make_token


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


def test_development_without_token_falls_back_to_default():
    """Local-dev convenience only. Production must never reach this path."""
    from auth.supabase_jwt import get_user_id

    assert get_user_id(None) == "default"


# --- Through the HTTP layer ------------------------------------------------

def test_protected_endpoint_rejects_request_without_token(client, production):
    assert client.get("/history").status_code == 401


def test_protected_endpoint_rejects_expired_token(client, production, auth_headers):
    resp = client.get("/history", headers=auth_headers("user-a", expires_in=-60))
    assert resp.status_code == 401


def test_admin_endpoints_reject_missing_and_wrong_secret(client):
    assert client.get("/admin/usage").status_code == 403
    assert client.get("/admin/usage", headers={"x-admin-secret": "wrong"}).status_code == 403
    assert client.get("/admin/analytics-data", headers={"x-admin-secret": "wrong"}).status_code == 403
