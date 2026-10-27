from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt
from passlib.context import CryptContext

from core.config import settings
from enums.user_enums import UserRole

logger = logging.getLogger(__name__)

# Инициализация контекста для безопасного хеширования паролей (bcrypt)
_pwd_context: Final[CryptContext] = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTService:
    """Сервис криптографических операций: хеширование, JWT, API-ключи."""

    def __init__(self) -> None:
        pass

    # ---------- PASSWORD HASHING ----------

    def hash_password(self, password: str) -> str:
        """Генерирует безопасный хеш пароля."""
        try:
            return _pwd_context.hash(password)
        except Exception as exc:
            logger.exception("hash_password: ошибка хеширования")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверяет соответствие пароля его хешу."""
        try:
            return _pwd_context.verify(plain_password, hashed_password)
        except Exception as exc:
            logger.exception("verify_password: ошибка проверки пароля")
            return False

    # ---------- JWT GENERATION ----------

    def create_access_token(self, user_id: int, role: UserRole) -> str:
        """Генерирует JWT access token."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode: dict[str, Any] = {
            "sub": str(user_id),  # str для совместимости с _parse_sub из core.auth
            "role": role.value if hasattr(role, "value") else role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }

        try:
            return jwt.encode(to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM)
        except Exception as exc:
            logger.exception("create_access_token: ошибка генерации JWT user_id=%s", user_id)
            raise

    def create_refresh_token(self, user_id: int) -> str:
        """Генерирует JWT refresh token с длительным сроком жизни."""
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }

        try:
            return jwt.encode(to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM)
        except Exception as exc:
            logger.exception("create_refresh_token: ошибка генерации JWT user_id=%s", user_id)
            raise

    # ---------- API KEYS ----------

    def generate_api_key(self) -> str:
        """Генерирует криптографически стойкий API-ключ."""
        try:
            return f"sk_live_{secrets.token_urlsafe(32)}"
        except Exception as exc:
            logger.exception("generate_api_key: ошибка генерации ключа")
            raise


jwt_service: Final[JWTService] = JWTService()