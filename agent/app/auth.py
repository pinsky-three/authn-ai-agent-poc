from __future__ import annotations

from fastapi import HTTPException, Request


def require_user(request: Request) -> tuple[str, str]:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    sub = request.headers.get("X-User-Sub")
    if not token or not sub:
        raise HTTPException(401, "Missing user context")
    return sub, token
