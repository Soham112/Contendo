"""Supabase JWT verification for FastAPI.

Uses PyJWT HS256 with SUPABASE_JWT_SECRET to verify Bearer tokens.

In non-production environments (ENVIRONMENT != "production"), requests without
an Authorization header fall back to user_id="default" so local development
works without Supabase credentials.
"""

import os
from typing import Optional

import jwt
from fastapi import Header, HTTPException

_SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "").lower()


def get_user_id(authorization: Optional[str] = None) -> str:
    """Extract and verify Supabase JWT; return the user_id (sub claim).

    Dev fallback: if ENVIRONMENT != "production" and no Authorization header
    is present, returns "default" so localhost works without Supabase credentials.
    """
    if not authorization:
        if _ENVIRONMENT != "production":
            return "default"
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format — expected 'Bearer <token>'")

    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(
            token,
            _SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
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
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")


async def get_user_id_dep(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency — extracts user_id from the Authorization header."""
    return get_user_id(authorization)
