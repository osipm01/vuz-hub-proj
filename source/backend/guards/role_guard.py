from core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List
import jwt


ALGORITHM = "HS256"

# Автоматически ищет заголовок "Authorization: Bearer <токен>"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_role(token: str = Depends(oauth2_scheme)) -> str:
    # Ошибка валидации токена -> 401
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось валидировать учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_JWT_KEY, algorithms=[ALGORITHM])
        role: str | None = payload.get("role")

        if role is None:
            raise credentials_exception

        return role

    except jwt.ExpiredSignatureError:
        # Истёкший access token -> 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # Любая другая проблема с токеном -> 401
        raise credentials_exception


def role_guard(allowed_roles: List[str]):
    async def role_dependency(user_role: str = Depends(get_current_role)):
        # Токен валиден, но роли не хватает -> 403
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен: недостаточно прав",
            )
        return user_role

    return role_dependency