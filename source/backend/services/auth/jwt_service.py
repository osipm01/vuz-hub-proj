from __future__ import annotations

import logging
from typing import Any, Final

import bcrypt
import jwt

from core.config import settings
from enums.user_enums import UserRole

logger = logging.getLogger(__name__)


class JWTService:
    """Сервис криптографических операций: хеширование, JWT, API-ключи."""

    def hash_password(self, password: str) -> str:
        try:
            # Превращаем пароль в байты, генерируем соль и хешируем
            pwd_bytes = password.encode("utf-8")
            salt = bcrypt.gensalt()
            hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
            # Возвращаем строковое представление для сохранения в БД
            return hashed_bytes.decode("utf-8")
        except Exception:
            logger.exception("hash_password: ошибка хеширования")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            # Переводим в байты обе строки и сравниваем безопасным методом checkpw
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except Exception:
            # Возвращаем False при любых ошибках декодирования или несоответствия форматов
            return False

    def create_access_token(self, user_id: int, role: UserRole) -> str:
        from datetime import datetime, timedelta, timezone

        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode: dict[str, Any] = {
            "sub": str(user_id),
            "role": role.value if hasattr(role, "value") else role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        try:
            return jwt.encode(to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM)
        except Exception:
            logger.exception("create_access_token: ошибка user_id=%s", user_id)
            raise

    def create_refresh_token(self, user_id: int) -> str:
        from datetime import datetime, timedelta, timezone

        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        try:
            return jwt.encode(to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM)
        except Exception:
            logger.exception("create_refresh_token: ошибка user_id=%s", user_id)
            raise

    def generate_api_key(self) -> str:
        import secrets
        try:
            return f"sk_live_{secrets.token_urlsafe(32)}"
        except Exception:
            logger.exception("generate_api_key: ошибка")
            raise


jwt_service: Final[JWTService] = JWTService()
