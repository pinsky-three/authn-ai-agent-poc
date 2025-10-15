from typing import TypedDict


class Profile(TypedDict, total=False):
    sub: str
    email: str
    roles: list[str]
