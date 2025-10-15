from typing import TypedDict


class SessionData(TypedDict):
    sub: str
    email: str
    roles: list[str]
    access_token: str
    refresh_token: str | None
