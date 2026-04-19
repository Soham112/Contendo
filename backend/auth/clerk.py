import json
import os
import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

security = HTTPBearer(auto_error=False)

def get_user_id(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        if ENVIRONMENT != "production":
            return "default"
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()

    # Try HS256 with legacy JWT secret first
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True}
            )
            return payload["sub"]
        except Exception:
            pass

    # Try RS256 via Supabase JWKS
    if SUPABASE_URL:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            resp = httpx.get(jwks_url, timeout=10)
            resp.raise_for_status()
            jwks = resp.json()

            # Find matching key
            matching_key = None
            for k in jwks.get("keys", []):
                if kid is None or k.get("kid") == kid:
                    matching_key = k
                    break

            if matching_key is None:
                raise ValueError("No matching key found in JWKS")

            # Use PyJWT's algorithm to load the key
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(matching_key)

            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience="authenticated",
                options={"verify_exp": True}
            )
            return payload["sub"]
        except Exception as e:
            if ENVIRONMENT != "production":
                return "default"
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    if ENVIRONMENT != "production":
        return "default"
    raise HTTPException(status_code=401, detail="Token verification failed")

async def get_user_id_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str:
    auth_header = f"Bearer {credentials.credentials}" if credentials else None
    return get_user_id(auth_header)
