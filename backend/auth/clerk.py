"""Clerk JWT verification for FastAPI.

Uses PyJWT + Clerk's JWKS endpoint to verify Bearer tokens.

In non-production environments (ENVIRONMENT != "production"), requests without
an Authorization header fall back to user_id="default" so local development
works without Clerk credentials.
"""

import json
import os
import time
from typing import Optional

import httpx
import jwt
from fastapi import Header, HTTPException
from jwt.algorithms import RSAAlgorithm

_CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "").lower()

# In-memory JWKS cache — refreshed at most once per hour.
_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # seconds


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    resp = httpx.get(
        "https://api.clerk.com/v1/jwks",
        headers={"Authorization": f"Bearer {_CLERK_SECRET_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_fetched_at = now
    return _jwks_cache


def _get_signing_key(token: str, jwks: dict):
    """Select the RSA public key from the JWKS matching the token's kid header."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key_data))
    raise jwt.InvalidTokenError("No matching key found in JWKS for kid=" + str(kid))


def get_user_id(authorization: Optional[str] = None) -> str:
    """Extract and verify Clerk JWT; return the user_id (sub claim).

    Dev fallback: if ENVIRONMENT != "production" and no Authorization header
    is present, returns "default" so localhost works without Clerk credentials.
    """
    if not authorization:
        if _ENVIRONMENT != "production":
            return "default"
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format — expected 'Bearer <token>'")

    token = authorization[len("Bearer "):]
    try:
        jwks = _get_jwks()
        signing_key = _get_signing_key(token, jwks)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")
        return user_id
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")


async def get_user_id_dep(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency — extracts user_id from the Authorization header."""
    return get_user_id(authorization)
