"""Supabase JWT verification for FastAPI.

Supports both HS256 (legacy JWT secret) and RS256 (JWKS endpoint).
Supabase issues RS256 tokens by default; HS256 is tried first for
backwards compatibility, then falls back to RS256 via JWKS.

In non-production environments (ENVIRONMENT != "production"), requests without
an Authorization header fall back to user_id="default" so local development
works without Supabase credentials.
"""

import json
import os
from typing import Optional

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "").lower()


def get_user_id(authorization: str | None = None) -> str:
    """Extract and verify Supabase JWT; return the user_id (sub claim).

    Tries HS256 first (legacy JWT secret), then falls back to RS256 via JWKS.

    Dev fallback: if ENVIRONMENT != "production" and no Authorization header
    is present, returns "default" so localhost works without Supabase credentials.
    """
    if not authorization or not authorization.startswith("Bearer "):
        if _ENVIRONMENT != "production":
            return "default"
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()

    # Try HS256 first (legacy JWT secret)
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload["sub"]
    except Exception:
        pass

    # Fall back to RS256 via JWKS
    try:
        jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        response = httpx.get(jwks_url, timeout=10)
        jwks = response.json()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next(k for k in jwks["keys"] if k.get("kid") == kid)
        public_key = RSAAlgorithm.from_jwk(json.dumps(key))
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="authenticated",
        )
        return payload["sub"]
    except Exception as e:
        if _ENVIRONMENT != "production":
            return "default"
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_user_id_dep(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency — extracts user_id from the Authorization header."""
    return get_user_id(authorization)
