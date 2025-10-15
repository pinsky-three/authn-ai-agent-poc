from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse

from .oidc import router as oidc_router
from .session import get_session
from .settings import settings
from .types import SessionData

app = FastAPI(title="BFF")
app.include_router(oidc_router)


def require_session(request: Request) -> SessionData:
    sid = request.cookies.get(settings.session_cookie_name)
    sess = get_session(sid) if sid else None
    if not sess:
        raise HTTPException(401, "Not authenticated")
    return sess


@app.get("/")
def root():
    return {"ok": True}


@app.get("/me")
def me(request: Request):
    sess = require_session(request)
    return {"sub": sess["sub"], "email": sess["email"], "roles": sess["roles"]}


@app.post("/run-agent")
async def run_agent(request: Request, payload: dict):
    sess = require_session(request)
    # Forward to agent with scoped access token (already aud=api://acme-api)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "http://agent:8081/run",
            headers={
                "Authorization": f"Bearer {sess['access_token']}",
                "X-User-Sub": sess["sub"],
            },
            json={"task": payload.get("task", "whoami")},
        )
    return JSONResponse(r.json(), status_code=r.status_code)
