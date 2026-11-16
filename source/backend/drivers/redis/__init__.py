"""
Асинхронный Redis-драйвер для кеширования.

Базовый функционал:
  - connect / close — жизненный цикл
  - get_json / set_json — сериализация dict/list/scalars
  - delete / delete_pattern — инвалидация по ключу или паттерну
  - smembers / sadd / srem — set-операции для тегирования
  - Круглая обёртка: при ошибках Redis не ломает запрос

Использование:
    driver = RedisDriver(url="redis://localhost:6379/0")
    await driver.connect()

    await driver.set_json("schedule:1", {"id": 1, "weekday": 2})
    data = await driver.get_json("schedule:1")

    await driver.close()
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Union

import redis.asyncio as aioredis
from redis.exceptions import RedisError

# ------------------------------------------------------------------ #
#  Типы
# ------------------------------------------------------------------ #

JsonValue = Union[
    None,
    bool,
    int,
    float,
    str,
    list["JsonValue"],
    dict[str, "JsonValue"],
]
Key = str
TTL = int  # секунды

# ------------------------------------------------------------------ #
#  Исключения (небольшие, чтобы не тянуть весь redis_driver_ini)
# ------------------------------------------------------------------ #


class RedisDriverError(Exception):
    """Базовое исключение Redis-драйвера."""

    pass


class RedisNotConnected(RedisDriverError):
    """Redis недоступен."""

    pass


class RedisSerializationError(RedisDriverError):
    """Ошибка сериализации JSON."""

    pass


# ------------------------------------------------------------------ #
#  Логгер
# ------------------------------------------------------------------ #

logger: logging.Logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  RedisDriver
# ------------------------------------------------------------------ #

DEFAULT_URL: str = "redis://localhost:6379/0"


class RedisDriver:
    """
    Минимальный async-драйвер Redis с JSON-поддержкой.

    Все публичные методы-async обернуты в safe-логике:
    при недоступности Redis — возвращается None / False,
    ошибки логируются, запрос не падает.
    """

    __slots__ = (
        "url",
        "key_prefix",
        "_client",
        "_socket_timeout",
        "_socket_connect_timeout",
    )

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        key_prefix: str = "",
        socket_timeout: float = 3.0,
        socket_connect_timeout: float = 3.0,
    ) -> None:
        self.url = url
        self.key_prefix = key_prefix
        self._client: Optional[aioredis.Redis] = None
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout

    # ---------------------------------------------------------- #
    #  Lifecycle
    # ---------------------------------------------------------- #

    async def connect(self) -> None:
        """Открыть пул соединений и проверить доступность Redis."""
        if self._client is not None:
            return

        try:
            client = aioredis.from_url(
                self.url,
                decode_responses=True,
                max_connections=20,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
            )
            await client.ping()
            self._client = client
            logger.info("Redis connected: %s", self.url)
        except RedisError as exc:
            logger.warning("Redis connection failed: %s", exc)
            raise RedisNotConnected(f"Cannot connect to Redis at {self.url}: {exc}") from exc

    async def close(self) -> None:
        if self._client is None:
            return
        client = self._client
        self._client = None
        try:
            await client.aclose()
            logger.info("Redis closed")
        except RedisError as exc:
            logger.warning("Error closing Redis: %s", exc)

    # ---------------------------------------------------------- #
    #  Helpers
    # ---------------------------------------------------------- #

    def _key(self, key: Key) -> Key:
        """Применить key_prefix."""
        if self.key_prefix:
            return f"{self.key_prefix}{key}"
        return key

    def _raw_client(self) -> aioredis.Redis:
        if self._client is None:
            raise RedisNotConnected("Call connect() before using the driver")
        return self._client

    # ---------------------------------------------------------- #
    #  JSON operations
    # ---------------------------------------------------------- #

    async def get_json(self, key: Key) -> Optional[JsonValue]:
        """Получить значение из Redis по ключу, десериализовать JSON."""
        if self._client is None:
            return None
        try:
            raw = await self._client.get(self._key(key))
            if raw is None:
                return None
            return json.loads(raw)
        except RedisError as exc:
            logger.warning("Redis GET error for key '%s': %s", key, exc)
            return None
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Invalid JSON in key '%s': %s", key, exc)
            return None

    async def set_json(
        self,
        key: Key,
        value: JsonValue,
        *,
        ttl: Optional[TTL] = None,
    ) -> bool:
        """Записать JSON-значение в Redis с опциональным TTL."""
        if self._client is None:
            logger.debug("Redis not connected, skipping set for key '%s'", key)
            return False
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            logger.warning("Cannot encode JSON for key '%s': %s", key, exc)
            return False
        try:
            if ttl is not None:
                await self._client.set(self._key(key), payload, ex=ttl)
            else:
                await self._client.set(self._key(key), payload)
            return True
        except RedisError as exc:
            logger.warning("Redis SET error for key '%s': %s", key, exc)
            return False

    # ---------------------------------------------------------- #
    #  Delete
    # ---------------------------------------------------------- #

    async def delete(self, *keys: Key) -> int:
        """Удалить ключи. Возвращает количество удалённых."""
        if self._client is None:
            return 0
        try:
            prefixed = [self._key(k) for k in keys]
            return int(await self._client.delete(*prefixed))
        except RedisError as exc:
            logger.warning("Redis DELETE error: %s", exc)
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """
        Удалить все ключи, matching паттерн.

        Redis не поддерживает DELETE с glob-паттерном напрямую,
        поэтому используем SCAN + DELETE для безопасной работы
        на продакшене (не блокирует Redis как KEYS).
        """
        if self._client is None:
            return 0
        count = 0
        try:
            cursor = 0
            prefixed_pattern = self._key(pattern)
            while True:
                cursor, keys_batch = await self._client.scan(
                    cursor=cursor, match=prefixed_pattern, count=100
                )
                if keys_batch:
                    deleted = int(await self._client.delete(*keys_batch))
                    count += deleted
                if cursor == 0:
                    break
        except RedisError as exc:
            logger.warning("Redis DELETE_PATTERN error for '%s': %s", pattern, exc)
            # Fallback: попробуем через KEYS (для небольших наборов)
            try:
                prefixed_pattern = self._key(pattern)
                keys_batch = await self._client.keys(prefixed_pattern)
                if keys_batch:
                    count = int(await self._client.delete(*keys_batch))
            except RedisError as exc2:
                logger.warning("Redis KEYS fallback also failed: %s", exc2)
        return count

    # ---------------------------------------------------------- #
    #  Set operations (для тегирования)
    # ---------------------------------------------------------- #

    async def smembers(self, key: Key) -> set[str]:
        """Получить все элементы set."""
        if self._client is None:
            return set()
        try:
            result = await self._client.smembers(self._key(key))
            return result if result else set()
        except RedisError as exc:
            logger.warning("Redis SMEMBERS error for key '%s': %s", key, exc)
            return set()

    async def sadd(self, key: Key, *members: str) -> int:
        """Добавить элементы в set. Возвращает количество добавленных."""
        if self._client is None:
            return 0
        try:
            return int(await self._client.sadd(self._key(key), *members))
        except RedisError as exc:
            logger.warning("Redis SADD error for key '%s': %s", key, exc)
            return 0

    async def srem(self, key: Key, *members: str) -> int:
        """Удалить элементы из set. Возвращает количество удалённых."""
        if self._client is None:
            return 0
        try:
            return int(await self._client.srem(self._key(key), *members))
        except RedisError as exc:
            logger.warning("Redis SREM error for key '%s': %s", key, exc)
            return 0

    # ---------------------------------------------------------- #
    #  String operations (базовые)
    # ---------------------------------------------------------- #

    async def get(self, key: Key) -> Optional[str]:
        """Получить строковое значение."""
        if self._client is None:
            return None
        try:
            return await self._client.get(self._key(key))
        except RedisError as exc:
            logger.warning("Redis GET error for key '%s': %s", key, exc)
            return None

    async def set(
        self,
        key: Key,
        value: str,
        *,
        ttl: Optional[TTL] = None,
    ) -> bool:
        """Записать строковое значение."""
        if self._client is None:
            return False
        try:
            if ttl is not None:
                await self._client.set(self._key(key), value, ex=ttl)
            else:
                await self._client.set(self._key(key), value)
            return True
        except RedisError as exc:
            logger.warning("Redis SET error for key '%s': %s", key, exc)
            return False
