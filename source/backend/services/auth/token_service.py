from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt
from jwt.exceptions import PyJWTError

from core.config import settings

logger = logging.getLogger(__name__)


class TokenService:
    """
    Генерация и проверка токенов:
      - access / refresh JWT для пользователей (CLIENT)
      - JWT для ботов (BOT)
      - JWT для интеграций (INTEGRATION)
      - opaque API-ключи
    """

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def encode(self, payload: dict[str, Any]) -> str:
        try:
            return jwt.encode(payload, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM)
        except PyJWTError:
            logger.exception("encode: ошибка кодирования JWT")
            raise

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, settings.SECRET_JWT_KEY, algorithms=[settings.ALGORITHM])
        except PyJWTError:
            logger.exception("decode: ошибка декодирования JWT")
            raise

    def create_access_token(self, user_id: int, role) -> str:
        now = self.now()
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "role": role.value if hasattr(role, "value") else role,
            "type": "access",
            "exp": expire,
            "iat": now,
        }
        return self.encode(payload)

    def create_refresh_token(self, user_id: int) -> str:
        now = self.now()
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": now,
        }
        return self.encode(payload)

    def generate_api_key(self, prefix: str = "sk_live_", nbytes: int = 32) -> str:
        try:
            return f"{prefix}{secrets.token_urlsafe(nbytes)}"
        except Exception:
            logger.exception("generate_api_key: prefix=%r", prefix)
            raise


token_service: Final[TokenService] = TokenService()
