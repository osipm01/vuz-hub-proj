from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.config import settings

logger = logging.getLogger(__name__)

# Заявки, которые не могут быть перезаписаны через extra_claims
_RESERVED_CLAIMS = frozenset(
    {"sub", "type", "exp", "iat", "role", "bot_id", "integration_id"}
)


class TokenService:
    """
    Генерация и проверка токенов:
      - access / refresh JWT для пользователей (CLIENT)
      - JWT для ботов (BOT)               — claim: bot_id
      - JWT для интеграций (INTEGRATION)  — claim: integration_id
      - opaque API-ключи
    """

    def encode(self, payload: dict[str, Any]) -> str:
        try:
            return jwt.encode(
                payload, settings.SECRET_JWT_KEY, algorithm=settings.ALGORITHM
            )
        except Exception:
            logger.exception("encode: ошибка кодирования JWT")
            raise

    def decode(self, token: str) -> dict[str, Any]:
        # P0-fix: require + type check
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_JWT_KEY,
                algorithms=[settings.ALGORITHM],
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_exp": True,
                },
            )
        except ExpiredSignatureError:
            logger.warning("decode: токен истёк")
            raise
        except InvalidTokenError:
            logger.warning("decode: невалидный токен")
            raise
        return payload

    def decode_with_type(self, token: str, expected_type: str) -> dict[str, Any]:
        """Расшифровать токен и проверить claim type."""
        payload = self.decode(token)
        if payload.get("type") != expected_type:
            raise InvalidTokenError(
                f"Ожидается тип токена '{expected_type}', "
                f"получено '{payload.get('type')}'"
            )
        return payload

    # ---------- CLIENT (USER) ----------

    def create_access_token(self, user_id: int, role: Any) -> str:
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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
        # P0-fix: extra_claims не перезаписывает reserved claims
        if extra_claims:
            for key, value in extra_claims.items():
                if key not in _RESERVED_CLAIMS:
                    payload[key] = value
        return self.encode(payload)

    # ---------- INTEGRATION ----------

    def create_integration_token(
        self,
        integration_id: int | str,
        *,
        expires_in_days: int | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
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
            for key, value in extra_claims.items():
                if key not in _RESERVED_CLAIMS:
                    payload[key] = value
        return self.encode(payload)

    # ---------- OPAQUE API KEYS ----------

    def generate_api_key(self, prefix: str = "sk_live_", entropy_bytes: int = 32) -> str:
        # P2-fix: nbytes → entropy_bytes (это байты энтропии, не длина ключа)
        return f"{prefix}{secrets.token_urlsafe(entropy_bytes)}"

    def generate_integration_key(self) -> str:
        return self.generate_api_key(prefix="int_live_")

    def generate_bot_key(self) -> str:
        return self.generate_api_key(prefix="bot_live_")

    def generate_webhook_secret(self, entropy_bytes: int = 32) -> str:
        return secrets.token_urlsafe(entropy_bytes)


token_service: Final[TokenService] = TokenService()
