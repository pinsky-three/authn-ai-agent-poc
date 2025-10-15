from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from .session import set_session
from .settings import settings

router = APIRouter()
oauth = OAuth()
oauth.register(
    name="okta",
    server_metadata_url=f"{settings.okta_issuer}/.well-known/openid-configuration",
    client_id=settings.okta_client_id,
    client_secret=settings.okta_client_secret,
    client_kwargs={"scope": f"openid profile email {settings.acme_scopes}"},
)


@router.get("/auth/login")
async def login(request: Request):
    redirect_uri = str(settings.oidc_redirect_uri)
    return await oauth.okta.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.okta.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    # Extract claims for session
    sub = userinfo.get("sub") or token.get("sub")
    email = userinfo.get("email")
    roles = userinfo.get("roles", [])
    resp = RedirectResponse(url="/me")
    set_session(
        resp,
        {
            "sub": sub,
            "email": email,
            "roles": roles,
            "access_token": token["access_token"],
            "refresh_token": token.get("refresh_token"),
        },
    )
    return resp
