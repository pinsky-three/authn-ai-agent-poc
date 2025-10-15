from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException

from .jwt_verify import verify

app = FastAPI(title="ACME API")


@app.get("/v1/whoami")
async def whoami(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer")
    token = authorization.split(" ", 1)[1]
    try:
        claims = await verify(token)
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")
    return {
        "sub": claims["sub"],
        "email": claims.get("email"),
        "roles": claims.get("roles", []),
    }
