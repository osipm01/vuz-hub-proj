from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine, Sequence
from enum import Enum
from typing import Any, Final, TypedDict

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError

from core.config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

AUTH_HEADER: Final[str] = "x-auth-type"
BOT_HEADER: Final[str] = "x-bot-token"
INTEGRATION_HEADER: Final[str] = "x-integration-key"
CLIENT_HEADER: Final[str] = "x-auth-token"

WWW_AUTHENTICATE_BEARER: Final[dict[str, str]] = {"WWW-Authenticate": "Bearer"}


class AuthType(str, Enum):
    BOT = "BOT"
    INTEGRATION = "INTEGRATION"
    CLIENT = "client"


class TokenPayload(TypedDict, total=False):
    sub: str
    role: str
    exp: int
    iat: int


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=WWW_AUTHENTICATE_BEARER,
    )


def forbidden(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def extract_token_from_request(request: Request, header_token: str | None) -> str:
    auth_type_raw = request.headers.get(AUTH_HEADER)

    if auth_type_raw is not None:
        try:
            auth_type = AuthType(auth_type_raw)
        except ValueError:
            logger.warning("Неизвестный %s=%r", AUTH_HEADER, auth_type_raw)
            raise unauthorized(f"Недопустимое значение {AUTH_HEADER}") from None
    else:
        auth_type = AuthType.CLIENT

    if auth_type is AuthType.BOT:
        token = request.headers.get(BOT_HEADER)
        if not token:
            logger.info("Отсутствует %s для auth_type=BOT", BOT_HEADER)
            raise unauthorized(f"Отсутствует {BOT_HEADER}")
        return token

    if auth_type is AuthType.INTEGRATION:
        token = request.headers.get(INTEGRATION_HEADER)
        if not token:
            logger.info("Отсутствует %s для auth_type=INTEGRATION", INTEGRATION_HEADER)
            raise unauthorized(f"Отсутствует {INTEGRATION_HEADER}")
        return token

    # AuthType.CLIENT
    token = (
        request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
        or request.headers.get(CLIENT_HEADER)
        or header_token
    )
    if not token:
        logger.info("Токен не найден: cookie=%s, %s, Authorization", settings.ACCESS_TOKEN_COOKIE_NAME, CLIENT_HEADER)
        raise unauthorized("Токен не найден ни в cookie, ни в заголовке")
    return token


async def get_token(
    request: Request,
    header_token: str | None = Depends(oauth2_scheme),
) -> str:
    return extract_token_from_request(request, header_token)


def decode_jwt(token: str) -> TokenPayload:
    try:
        payload: TokenPayload = jwt.decode(
            token,
            settings.SECRET_JWT_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        logger.info("Срок действия JWT истёк")
        raise unauthorized("Срок действия токена истек") from exc
    except InvalidTokenError as exc:
        logger.warning("Невалидный JWT: %s", exc)
        raise unauthorized("Не удалось валидировать учетные данные") from exc
    except PyJWTError as exc:
        logger.exception("Неожиданная ошибка при декодировании JWT")
        raise unauthorized("Не удалось валидировать учетные данные") from exc
    return payload


async def get_current_role(token: str = Depends(get_token)) -> str:
    payload = decode_jwt(token)

    role = payload.get("role")
    if not isinstance(role, str) or not role:
        logger.warning("В JWT отсутствует роль: sub=%r", payload.get("sub"))
        raise unauthorized("В токене отсутствует роль")

    return role


def role_guard(
    allowed_roles: Sequence[str],
) -> Callable[..., Coroutine[Any, Any, str]]:
    allowed = frozenset(allowed_roles)

    async def role_dependency(user_role: str = Depends(get_current_role)) -> str:
        if user_role not in allowed:
            logger.info("Доступ запрещён для роли=%r; разрешено=%r", user_role, allowed)
            raise forbidden("Доступ запрещен: недостаточно прав")
        return user_role

    return role_dependency