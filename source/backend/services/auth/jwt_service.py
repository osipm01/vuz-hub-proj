from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import bcrypt
import jwt

from core.config import settings
from enums.user_enums import UserRole

logger = logging.getLogger(__name__)

# Максимальная длина пароля для bcrypt — 72 байта
_BCRYPT_MAX_LENGTH = 72


class JWTService:
    """Сервис криптографических операций: хеширование, JWT, API-ключи."""

    def hash_password(self, password: str) -> str:
        # P0-fix: bcrypt молча обрезает пароли длиннее 72 байт → коллизии
        if len(password.encode("utf-8")) > _BCRYPT_MAX_LENGTH:
            raise ValueError(
                f"Длина пароля превышает лимит bcrypt ({_BCRYPT_MAX_LENGTH} байт)"
            )
        try:
            pwd_bytes = password.encode("utf-8")
            salt = bcrypt.gensalt()
            hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
            return hashed_bytes.decode("utf-8")
        except Exception:
            logger.exception("hash_password: ошибка хеширования")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception:
            return False

    def create_access_token(self, user_id: int, role: UserRole) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode: dict[str, Any] = {
            "sub": str(user_id),
            "role": role.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        try:
            return jwt.encode(
                to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM
            )
        except Exception:
            logger.exception("create_access_token: ошибка user_id=%s", user_id)
            raise

    def create_refresh_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        to_encode: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        try:
            return jwt.encode(
                to_encode, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM
            )
        except Exception:
            logger.exception("create_refresh_token: ошибка user_id=%s", user_id)
            raise

    def generate_api_key(self) -> str:
        return f"sk_live_{secrets.token_urlsafe(32)}"


jwt_service: Final[JWTService] = JWTService()
