from __future__ import annotations

import httpx

from .types import Profile


async def acme_whoami(access_token: str) -> Profile:
    """Call ACME API through gateway to get user profile."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "http://gateway:8000/acme/v1/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()
