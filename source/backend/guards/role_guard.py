from collections.abc import Sequence
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_token(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    # 1) Сначала httponly-cookie
    token = request.cookies.get(settings.SECRET_JWT_KEY)

    # 2) Если cookie нет — берём из заголовка (fallback для старых клиентов)
    if not token:
        token = header_token

    if not token:
        raise _unauthorized("Токен не найден ни в cookie, ни в заголовке")

    return token


async def get_current_role(token: str = Depends(get_token)) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_JWT_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError:
        raise _unauthorized("Срок действия токена истек")
    except InvalidTokenError:
        raise _unauthorized("Не удалось валидировать учетные данные")

    role = payload.get("role")
    if not isinstance(role, str) or not role:
        raise _unauthorized("В токене отсутствует роль")

    return role


def role_guard(allowed_roles: Sequence[str]):
    allowed = frozenset(allowed_roles)

    async def role_dependency(user_role: str = Depends(get_current_role)) -> str:
        if user_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен: недостаточно прав",
            )
        return user_role

    return role_dependency