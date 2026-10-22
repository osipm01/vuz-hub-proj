from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Final, Literal, Sequence

import jwt

from core.config import settings

logger = logging.getLogger(__name__)

TokenType = Literal["integration", "bot"]

_ALGORITHM: Final[str] = settings.ALGORITHM
_SECRET: Final[bytes] = settings.SECRET_JWT_KEY.encode()


# ============================================================
# МОДЕЛИ PAYLOAD
# ============================================================
@dataclass(frozen=True, slots=True)
class IntegrationTokenPayload:
    issued_at: int
    expires_at: int              # -1 = бессрочно
    key: str                     # HMAC-SHA256(issued_at, SECRET)
    token_type: Literal["integration"]
    integration_id: str
    scopes: tuple[str, ...] = ()

    def is_expired(self, now: int | None = None) -> bool:
        if self.expires_at == -1:
            return False
        return (now or _now_ts()) > self.expires_at


@dataclass(frozen=True, slots=True)
class BotTokenPayload:
    issued_at: int
    expires_at: int              # -1 = бессрочно
    key: str                     # HMAC-SHA256(issued_at, SECRET)
    token_type: Literal["bot"]
    bot_id: str
    permissions: tuple[str, ...] = ()

    def is_expired(self, now: int | None = None) -> bool:
        if self.expires_at == -1:
            return False
        return (now or _now_ts()) > self.expires_at


ServiceTokenPayload = IntegrationTokenPayload | BotTokenPayload


# ============================================================
# ВСПОМОГАТЕЛЬНОЕ
# ============================================================
def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _make_key(issued_at: int) -> str:
    """HMAC-SHA256 от даты выдачи с секретом — детерминированно и проверяемо."""
    return hmac.new(_SECRET, str(issued_at).encode(), hashlib.sha256).hexdigest()


def _key_is_valid(issued_at: int, key: str) -> bool:
    return hmac.compare_digest(key, _make_key(issued_at))


def _encode(payload: ServiceTokenPayload) -> str:
    return jwt.encode(asdict(payload), _SECRET, algorithm=_ALGORITHM)


def _decode_raw(token: str) -> dict[str, Any] | None:
    """
    Декодирует JWT без проверки exp (у нас свой expires_at, где -1 = бессрочно).
    Возвращает None при любой ошибке подписи/формата.
    """
    try:
        return jwt.decode(
            token,
            _SECRET,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.ExpiredSignatureError:
        # не должно случаться при verify_exp=False, но на всякий
        logger.info("JWT истёк (exp)")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Невалидный JWT: %s", exc)
        return None


# ============================================================
# ГЕНЕРАЦИЯ
# ============================================================
def generate_integration_token(
    *,
    integration_id: str,
    scopes: Sequence[str] = (),
    ttl_seconds: int = -1,
) -> str:
    """Генерирует integration-JWT. ttl_seconds=-1 → бессрочно."""
    issued_at = _now_ts()
    payload = IntegrationTokenPayload(
        issued_at=issued_at,
        expires_at=-1 if ttl_seconds == -1 else issued_at + ttl_seconds,
        key=_make_key(issued_at),
        token_type="integration",
        integration_id=integration_id,
        scopes=tuple(scopes),
    )
    token = _encode(payload)
    logger.info(
        "Сгенерирован integration-токен: id=%r ttl=%s scopes=%r",
        integration_id, ttl_seconds, payload.scopes,
    )
    return token


def generate_bot_token(
    *,
    bot_id: str,
    permissions: Sequence[str] = (),
    ttl_seconds: int = -1,
) -> str:
    """Генерирует bot-JWT. ttl_seconds=-1 → бессрочно."""
    issued_at = _now_ts()
    payload = BotTokenPayload(
        issued_at=issued_at,
        expires_at=-1 if ttl_seconds == -1 else issued_at + ttl_seconds,
        key=_make_key(issued_at),
        token_type="bot",
        bot_id=bot_id,
        permissions=tuple(permissions),
    )
    token = _encode(payload)
    logger.info(
        "Сгенерирован bot-токен: id=%r ttl=%s permissions=%r",
        bot_id, ttl_seconds, payload.permissions,
    )
    return token


# ============================================================
# ВАЛИДАЦИЯ
# ============================================================
def _validate_common(token: str, expected: TokenType) -> dict[str, Any] | None:
    data = _decode_raw(token)
    if data is None:
        return None

    if data.get("token_type") != expected:
        logger.info(
            "Неверный тип токена: ожидался %r, получен %r",
            expected, data.get("token_type"),
        )
        return None

    issued_at = data.get("issued_at")
    expires_at = data.get("expires_at")
    key = data.get("key")

    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        logger.warning("Некорректные issued_at/expires_at: %r / %r", issued_at, expires_at)
        return None
    if not isinstance(key, str) or not _key_is_valid(issued_at, key):
        logger.warning("Невалидный key для issued_at=%r", issued_at)
        return None
    if expires_at != -1 and _now_ts() > expires_at:
        logger.info("Срок действия токена истёк: expires_at=%r", expires_at)
        return None

    return data


def validation_integration_token(token: str) -> IntegrationTokenPayload | None:
    data = _validate_common(token, "integration")
    if data is None:
        return None
    integration_id = data.get("integration_id")
    if not isinstance(integration_id, str) or not integration_id:
        logger.warning("В integration-токене отсутствует integration_id")
        return None
    scopes = data.get("scopes") or ()
    if not isinstance(scopes, (list, tuple)):
        logger.warning("Некорректный scopes: %r", scopes)
        return None
    return IntegrationTokenPayload(
        issued_at=data["issued_at"],
        expires_at=data["expires_at"],
        key=data["key"],
        token_type="integration",
        integration_id=integration_id,
        scopes=tuple(str(s) for s in scopes),
    )


def validation_bot_token(token: str) -> BotTokenPayload | None:
    data = _validate_common(token, "bot")
    if data is None:
        return None
    bot_id = data.get("bot_id")
    if not isinstance(bot_id, str) or not bot_id:
        logger.warning("В bot-токене отсутствует bot_id")
        return None
    permissions = data.get("permissions") or ()
    if not isinstance(permissions, (list, tuple)):
        logger.warning("Некорректный permissions: %r", permissions)
        return None
    return BotTokenPayload(
        issued_at=data["issued_at"],
        expires_at=data["expires_at"],
        key=data["key"],
        token_type="bot",
        bot_id=bot_id,
        permissions=tuple(str(p) for p in permissions),
    )