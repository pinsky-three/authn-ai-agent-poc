from __future__ import annotations

import json

import redis
from fastapi import Response
from itsdangerous import BadSignature, TimestampSigner

from .settings import settings
from .types import SessionData

r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
signer = TimestampSigner(settings.session_secret)


def set_session(resp: Response, data: SessionData) -> str:
    sid = signer.sign(data["sub"]).decode()
    r.setex(f"sess:{sid}", 3600 * 8, json.dumps(data))
    resp.set_cookie(settings.session_cookie_name, sid, httponly=True, samesite="Lax")
    return sid


def get_session(sid: str) -> SessionData | None:
    try:
        _ = signer.unsign(sid, max_age=3600 * 12)
    except BadSignature:
        return None
    raw = r.get(f"sess:{sid}")
    return json.loads(raw) if raw else None
