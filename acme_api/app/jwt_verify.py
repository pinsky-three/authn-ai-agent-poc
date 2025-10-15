from __future__ import annotations

import time
from typing import Any

import httpx
from cachetools import TTLCache
from jose import jwk, jwt

from .settings import settings

ISS = settings.okta_issuer
AUD = settings.acme_audience
JWKS_URI = f"{ISS}/v1/keys"
_cache: TTLCache = TTLCache(maxsize=1, ttl=300)


async def fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Okta, cached for 5 minutes."""
    if "jwks" in _cache:
        return _cache["jwks"]
    async with httpx.AsyncClient(timeout=5) as c:
        resp = await c.get(JWKS_URI)
        resp.raise_for_status()
        data = resp.json()
        _cache["jwks"] = data
        return data


async def verify(token: str) -> dict[str, Any]:
    """Verify JWT signature and claims against Okta JWKS."""
    headers = jwt.get_unverified_header(token)
    kid = headers["kid"]
    jwks = await fetch_jwks()
    key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key:
        raise ValueError("kid not found")
    claims = jwt.get_unverified_claims(token)
    if claims.get("iss") != ISS:
        raise ValueError("iss mismatch")
    if claims.get("aud") != AUD:
        raise ValueError("aud mismatch")
    if time.time() > claims["exp"]:
        raise ValueError("token expired")
    # Signature verification
    jwt.decode(
        token,
        jwk.construct(key),
        audience=AUD,
        issuer=ISS,
        options={"verify_aud": True},
    )
    return claims
