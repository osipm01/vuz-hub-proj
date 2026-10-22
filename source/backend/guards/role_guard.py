from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError

from core.config import settings
from guards.data_validation import (
    BotTokenPayload,
    IntegrationTokenPayload,
    validation_bot_token,
    validation_integration_token,
)
from enums.auth_type_enum import AuthType
from enums.user_enums import UserRole
from interfaces.auth_headers import (
    AUTH_HEADER,
    BOT_HEADER,
    CLIENT_HEADER,
    INTEGRATION_HEADER,
    WWW_AUTHENTICATE_BEARER,
)
from interfaces.token_paylod import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

PrincipalKind = Literal["user", "bot", "integration"]


# ============================================================
# PRINCIPAL
# ============================================================
@dataclass(frozen=True, slots=True)
class Principal:
    kind: PrincipalKind
    role: UserRole | None = None
    user_id: int | None = None
    bot: BotTokenPayload | None = None
    integration: IntegrationTokenPayload | None = None


# ============================================================
# ОШИБКИ
# ============================================================
def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=WWW_AUTHENTICATE_BEARER,
    )


def forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ============================================================
# ИЗВЛЕЧЕНИЕ / ДЕКОД
# ============================================================
def extract_auth_type(request: Request) -> AuthType:
    raw = request.headers.get(AUTH_HEADER)
    if raw is None:
        return AuthType.CLIENT
    try:
        return AuthType(raw)
    except ValueError:
        logger.warning("Неизвестный %s=%r", AUTH_HEADER, raw)
        raise unauthorized(f"Недопустимое значение {AUTH_HEADER}") from None


def extract_token_from_request(request: Request, header_token: str | None) -> str:
    auth_type = extract_auth_type(request)

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
        logger.info(
            "Токен не найден: cookie=%s, %s, Authorization",
            settings.ACCESS_TOKEN_COOKIE_NAME, CLIENT_HEADER,
        )
        raise unauthorized("Токен не найден ни в cookie, ни в заголовке")
    return token


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


def _parse_sub(sub: Any) -> int | None:
    if isinstance(sub, int):
        return sub
    if isinstance(sub, str) and sub.isdigit():
        return int(sub)
    return None


def _parse_role(raw: Any) -> UserRole:
    if not isinstance(raw, str) or not raw:
        logger.warning("В JWT отсутствует роль: role=%r", raw)
        raise unauthorized("В токене отсутствует роль")
    try:
        return UserRole(raw)
    except ValueError:
        logger.warning("Неизвестная роль в JWT: %r", raw)
        raise unauthorized("Неизвестная роль в токене") from None


# ============================================================
# PRINCIPAL DEPENDENCY
# ============================================================
async def get_principal(
    request: Request,
    header_token: str | None = Depends(oauth2_scheme),
) -> Principal:
    auth_type = extract_auth_type(request)

    if auth_type is AuthType.BOT:
        token = request.headers.get(BOT_HEADER)
        if not token:
            raise unauthorized(f"Отсутствует {BOT_HEADER}")
        payload = validation_bot_token(token)
        if payload is None:
            raise unauthorized("Невалидный bot-токен")
        logger.debug("Principal=bot id=%r", payload.bot_id)
        return Principal(kind="bot", bot=payload)

    if auth_type is AuthType.INTEGRATION:
        token = request.headers.get(INTEGRATION_HEADER)
        if not token:
            raise unauthorized(f"Отсутствует {INTEGRATION_HEADER}")
        payload = validation_integration_token(token)
        if payload is None:
            raise unauthorized("Невалидный integration-токен")
        logger.debug("Principal=integration id=%r", payload.integration_id)
        return Principal(kind="integration", integration=payload)

    # AuthType.CLIENT
    token = extract_token_from_request(request, header_token)
    data = decode_jwt(token)
    role = _parse_role(data.get("role"))
    user_id = _parse_sub(data.get("sub"))
    logger.debug(
        "Principal=user sub=%r user_id=%s role=%s",
        data.get("sub"), user_id, role.value,
    )
    return Principal(kind="user", role=role, user_id=user_id)


# ============================================================
# BACKWARD-COMPAT
# ============================================================

async def get_token(
    request: Request,
    header_token: str | None = Depends(oauth2_scheme),
) -> str:
    return extract_token_from_request(request, header_token)


async def get_current_role(token: str = Depends(get_token)) -> UserRole:
    """
    Совместимость со старым API.
    Возвращает только роль (для сценариев, где Principal не нужен).
    """
    data = decode_jwt(token)
    return _parse_role(data.get("role"))



# ============================================================
# ROLE GUARD
# ============================================================
def _auth_type_to_kind(t: AuthType) -> str:
    return {
        AuthType.CLIENT: "user",
        AuthType.BOT: "bot",
        AuthType.INTEGRATION: "integration",
    }[t]


def role_guard(
    allowed_roles: Sequence[UserRole],
    allowed_kinds: set[AuthType],
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """
    Проверка доступа:
      - user: role должна быть в allowed_roles, kind=CLIENT должен быть в allowed_kinds
      - bot/integration: роли нет; доступ только если их kind указан в allowed_kinds
    """
    allowed_roles_fs: Final[frozenset[UserRole]] = frozenset(allowed_roles)
    allowed_kinds_fs: Final[frozenset[PrincipalKind]] = frozenset(
        _auth_type_to_kind(t) for t in allowed_kinds
    )

    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.kind not in allowed_kinds_fs:
            logger.info(
                "Доступ запрещён: kind=%r; разрешено kinds=%r",
                principal.kind, sorted(allowed_kinds_fs),
            )
            raise forbidden("Доступ запрещен: недопустимый тип клиента")

        if principal.kind == "user":
            if principal.role is None or principal.role not in allowed_roles_fs:
                logger.info(
                    "Доступ запрещён для роли=%r; разрешено=%r",
                    principal.role, sorted(r.value for r in allowed_roles_fs),
                )
                raise forbidden("Доступ запрещен: недостаточно прав")

        return principal

    return dependency