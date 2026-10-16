from typing import TypedDict


class TokenPayload(TypedDict, total=False):
    sub: str
    role: str
    exp: int
    iat: int