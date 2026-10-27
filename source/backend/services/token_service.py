from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt
from jwt.exceptions import PyJWTError

from core.config import settings
from enums.user_enums import UserRole

logger = logging.getLogger(__name__)


class TokenService:
    """
    Генерация и проверка токенов:
      - access / refresh JWT для пользователей (CLIENT)
      - JWT для ботов (BOT)               — claim: bot_id
      - JWT для интеграций (INTEGRATION)  — claim: integration_id
      - opaque API-ключи (sk_live_..., int_live_..., bot_live_...)
    """

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def encode(self, payload: dict[str, Any]) -> str:
        try:
            return jwt.encode(
                payload,
                settings.SECRET_JWT_KEY,
                algorithm=settings.ALGORITHM,
            )
        except PyJWTError:
            logger.exception("encode: ошибка кодирования JWT")
            raise

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                settings.SECRET_JWT_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except PyJWTError:
            logger.exception("decode: ошибка декодирования JWT")
            raise

    # ---------- CLIENT (USER) ----------

    def create_access_token(self, user_id: int, role: UserRole) -> str:
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

    # ---------- BOT ----------

    def create_bot_token(
        self,
        bot_id: int | str,
        *,
        expires_in_days: int | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = self.now()
        expire = (
            now + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        payload: dict[str, Any] = {
            "bot_id": bot_id,
            "type": "bot",
            "exp": expire,
            "iat": now,
        }
        if extra_claims:
            payload.update(extra_claims)
        return self.encode(payload)

    # ---------- INTEGRATION ----------

    def create_integration_token(
        self,
        integration_id: int | str,
        *,
        expires_in_days: int | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = self.now()
        expire = (
            now + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        payload: dict[str, Any] = {
            "integration_id": integration_id,
            "type": "integration",
            "exp": expire,
            "iat": now,
        }
        if extra_claims:
            payload.update(extra_claims)
        return self.encode(payload)

    # ---------- OPAQUE API KEYS ----------

    def generate_api_key(self, *, prefix: str = "sk_live_", nbytes: int = 32) -> str:
        try:
            return f"{prefix}{secrets.token_urlsafe(nbytes)}"
        except Exception:
            logger.exception("generate_api_key: prefix=%r", prefix)
            raise

    def generate_integration_key(self) -> str:
        return self.generate_api_key(prefix="int_live_")

    def generate_bot_key(self) -> str:
        return self.generate_api_key(prefix="bot_live_")

    def generate_webhook_secret(self, nbytes: int = 32) -> str:
        try:
            return secrets.token_urlsafe(nbytes)
        except Exception:
            logger.exception("generate_webhook_secret: nbytes=%r", nbytes)
            raise


token_service: Final[TokenService] = TokenService()