"""
Асинхронный Redis-драйвер со строгой типизацией.

Принципы:
  - публичные атрибуты вместо `_` для внутренних полей (см. `__slots__`);
  - все redis-исключения транслируются в иерархию `RedisDriverError`;
  - опциональные ретраи для сетевых ошибок;
  - строгие типы для возвращаемых значений (str, int, dict, list, set).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import TracebackType
from typing import AsyncIterator, Final, Literal, Optional, Self

import redis.asyncio as aioredis
from redis.asyncio.client import Pipeline
from redis.exceptions import RedisError

from app.drivers.exceptions import (
    RedisDriverError,
    RedisNotInitialized,
    RedisSerializationError,
    translate,
)
from app.drivers.retry import RetryConfig, run_with_retry
from app.drivers.types import JsonValue, Key, RawValue, RedisValue, TTL, T_json

DEFAULT_URL: Final[str] = "redis://localhost:6379/0"


class RedisDriver:
    """
    Асинхронный драйвер Redis.

    Пример:
        driver = RedisDriver(url="redis://localhost:6379/0", key_prefix="app:")
        await driver.connect()

        await driver.set("k", "v", ttl=60)
        value: str | None = await driver.get("k")

        await driver.set_json("user:1", {"id": 1, "name": "Alice"})
        user: dict[str, JsonValue] | None = await driver.get_json("user:1")

        await driver.close()
    """

    __slots__ = (
        "url",
        "decode_responses",
        "max_connections",
        "socket_timeout",
        "socket_connect_timeout",
        "health_check_interval",
        "key_prefix",
        "retry",
        "client",
    )

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        decode_responses: bool = True,
        max_connections: int = 20,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        health_check_interval: int = 30,
        key_prefix: str = "",
        retry: RetryConfig | None = None,
    ) -> None:
        if max_connections < 1:
            raise ValueError("max_connections must be >= 1")
        if socket_timeout <= 0 or socket_connect_timeout <= 0:
            raise ValueError("timeouts must be positive")

        self.url = url
        self.decode_responses = decode_responses
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.health_check_interval = health_check_interval
        self.key_prefix = key_prefix
        self.retry = retry
        self.client: aioredis.Redis | None = None

    # -------------------------------------------------------------- #
    # lifecycle
    # -------------------------------------------------------------- #

    async def connect(self) -> None:
        """Открыть пул соединений и проверить доступность Redis."""
        if self.client is not None:
            return

        client = aioredis.from_url(
            self.url,
            decode_responses=self.decode_responses,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            health_check_interval=self.health_check_interval,
        )
        try:
            await client.ping()
        except RedisError as exc:
            await client.aclose()
            raise translate(exc) from exc

        self.client = client

    async def close(self) -> None:
        if self.client is None:
            return
        client, self.client = self.client, None
        try:
            await client.aclose()
        except RedisError as exc:
            raise translate(exc) from exc

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def require_client(self) -> aioredis.Redis:
        """Вернуть клиент или упасть с `RedisNotInitialized`."""
        if self.client is None:
            raise RedisNotInitialized("Call connect() before using the driver")
        return self.client

    # -------------------------------------------------------------- #
    # helpers
    # -------------------------------------------------------------- #

    def k(self, key: Key) -> Key:
        """Применить key_prefix."""
        return f"{self.key_prefix}{key}" if self.key_prefix else key

    def strip(self, key: Key) -> Key:
        """Снять key_prefix (для keys/scan_iter)."""
        return key[len(self.key_prefix):] if self.key_prefix and key.startswith(self.key_prefix) else key

    async def run(self, coro_factory):
        """
        Универсальная обёртка:
          - транслирует redis-исключения;
          - при `retry` повторяет сетевые ошибки.
        """
        async def once():
            try:
                return await coro_factory()
            except RedisError as exc:
                raise translate(exc) from exc

        if self.retry is None:
            return await once()
        return await run_with_retry(once, self.retry)

    # -------------------------------------------------------------- #
    # health / utils
    # -------------------------------------------------------------- #

    async def ping(self) -> bool:
        try:
            return bool(await self.require_client().ping())
        except RedisError:
            return False

    async def exists(self, key: Key) -> bool:
        return bool(await self.run(lambda: self.require_client().exists(self.k(key))))

    async def delete(self, *keys: Key) -> int:
        if not keys:
            return 0
        return int(await self.run(lambda: self.require_client().delete(*(self.k(x) for x in keys))))

    async def expire(self, key: Key, seconds: TTL) -> bool:
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        return bool(await self.run(lambda: self.require_client().expire(self.k(key), seconds)))

    async def ttl(self, key: Key) -> int:
        return int(await self.run(lambda: self.require_client().ttl(self.k(key))))

    async def keys(self, pattern: str = "*") -> list[Key]:
        raw = await self.run(lambda: self.require_client().keys(self.k(pattern)))
        return [self.strip(x) for x in raw]

    async def scan_iter(self, pattern: str = "*", count: int = 100) -> AsyncIterator[Key]:
        if count < 1:
            raise ValueError("count must be >= 1")
        async for key in self.require_client().scan_iter(match=self.k(pattern), count=count):
            yield self.strip(key)

    # -------------------------------------------------------------- #
    # strings
    # -------------------------------------------------------------- #

    async def get(self, key: Key) -> RawValue:
        return await self.run(lambda: self.require_client().get(self.k(key)))

    async def set(
        self,
        key: Key,
        value: RedisValue,
        *,
        ttl: Optional[TTL] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        if nx and xx:
            raise ValueError("nx and xx are mutually exclusive")
        return bool(
            await self.run(
                lambda: self.require_client().set(
                    self.k(key), value, ex=ttl, nx=nx, xx=xx
                )
            )
        )

    async def getset(self, key: Key, value: RedisValue) -> RawValue:
        return await self.run(lambda: self.require_client().getset(self.k(key), value))

    async def mget(self, *keys: Key) -> list[RawValue]:
        if not keys:
            return []
        return await self.run(lambda: self.require_client().mget(*(self.k(x) for x in keys)))

    async def mset(self, mapping: dict[Key, RedisValue]) -> bool:
        if not mapping:
            return True
        prefixed = {self.k(x): v for x, v in mapping.items()}
        return bool(await self.run(lambda: self.require_client().mset(prefixed)))

    # -------------------------------------------------------------- #
    # counters
    # -------------------------------------------------------------- #

    async def incr(self, key: Key, amount: int = 1) -> int:
        return int(await self.run(lambda: self.require_client().incrby(self.k(key), amount)))

    async def decr(self, key: Key, amount: int = 1) -> int:
        return int(await self.run(lambda: self.require_client().decrby(self.k(key), amount)))

    # -------------------------------------------------------------- #
    # JSON
    # -------------------------------------------------------------- #

    async def set_json(
        self,
        key: Key,
        value: JsonValue,
        *,
        ttl: Optional[TTL] = None,
    ) -> bool:
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            raise RedisSerializationError(f"Cannot encode JSON for key '{key}': {exc}") from exc
        return await self.set(key, payload, ttl=ttl)

    async def get_json(self, key: Key) -> JsonValue | None:
        raw = await self.get(key)
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else raw
        try:
            return json.loads(text)
        except (ValueError, TypeError) as exc:
            raise RedisSerializationError(f"Invalid JSON in key '{key}'") from exc

    # -------------------------------------------------------------- #
    # hashes
    # -------------------------------------------------------------- #

    async def hset(self, key: Key, mapping: dict[str, RedisValue]) -> int:
        if not mapping:
            return 0
        return int(await self.run(lambda: self.require_client().hset(self.k(key), mapping=mapping)))

    async def hget(self, key: Key, field: str) -> RawValue:
        return await self.run(lambda: self.require_client().hget(self.k(key), field))

    async def hgetall(self, key: Key) -> dict[str, str]:
        return await self.run(lambda: self.require_client().hgetall(self.k(key))) or {}

    async def hdel(self, key: Key, *fields: str) -> int:
        if not fields:
            return 0
        return int(await self.run(lambda: self.require_client().hdel(self.k(key), *fields)))

    async def hexists(self, key: Key, field: str) -> bool:
        return bool(await self.run(lambda: self.require_client().hexists(self.k(key), field)))

    async def hincrby(self, key: Key, field: str, amount: int = 1) -> int:
        return int(
            await self.run(lambda: self.require_client().hincrby(self.k(key), field, amount))
        )

    # -------------------------------------------------------------- #
    # lists
    # -------------------------------------------------------------- #

    async def lpush(self, key: Key, *values: RedisValue) -> int:
        return int(await self.run(lambda: self.require_client().lpush(self.k(key), *values)))

    async def rpush(self, key: Key, *values: RedisValue) -> int:
        return int(await self.run(lambda: self.require_client().rpush(self.k(key), *values)))

    async def lrange(self, key: Key, start: int = 0, end: int = -1) -> list[str]:
        return await self.run(lambda: self.require_client().lrange(self.k(key), start, end))

    async def lpop(self, key: Key) -> RawValue:
        return await self.run(lambda: self.require_client().lpop(self.k(key)))

    async def rpop(self, key: Key) -> RawValue:
        return await self.run(lambda: self.require_client().rpop(self.k(key)))

    async def llen(self, key: Key) -> int:
        return int(await self.run(lambda: self.require_client().llen(self.k(key))))

    async def ltrim(self, key: Key, start: int, end: int) -> bool:
        return bool(await self.run(lambda: self.require_client().ltrim(self.k(key), start, end)))

    # -------------------------------------------------------------- #
    # sets
    # -------------------------------------------------------------- #

    async def sadd(self, key: Key, *members: RedisValue) -> int:
        return int(await self.run(lambda: self.require_client().sadd(self.k(key), *members)))

    async def smembers(self, key: Key) -> set[str]:
        return await self.run(lambda: self.require_client().smembers(self.k(key))) or set()

    async def srem(self, key: Key, *members: RedisValue) -> int:
        return int(await self.run(lambda: self.require_client().srem(self.k(key), *members)))

    async def sismember(self, key: Key, member: RedisValue) -> bool:
        return bool(await self.run(lambda: self.require_client().sismember(self.k(key), member)))

    # -------------------------------------------------------------- #
    # sorted sets
    # -------------------------------------------------------------- #

    async def zadd(self, key: Key, mapping: dict[str, float]) -> int:
        if not mapping:
            return 0
        return int(await self.run(lambda: self.require_client().zadd(self.k(key), mapping)))

    async def zrange(
        self,
        key: Key,
        start: int = 0,
        end: int = -1,
        *,
        withscores: bool = False,
        desc: bool = False,
    ) -> list[str] | list[tuple[str, float]]:
        return await self.run(
            lambda: self.require_client().zrange(
                self.k(key), start, end, withscores=withscores, desc=desc
            )
        )

    async def zrem(self, key: Key, *members: RedisValue) -> int:
        return int(await self.run(lambda: self.require_client().zrem(self.k(key), *members)))

    async def zincrby(self, key: Key, member: str, amount: float = 1.0) -> float:
        return float(
            await self.run(lambda: self.require_client().zincrby(self.k(key), amount, member))
        )

    # -------------------------------------------------------------- #
    # pipeline
    # -------------------------------------------------------------- #

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True) -> AsyncIterator[Pipeline]:
        """
        Атомарный batch:

            async with driver.pipeline() as pipe:
                pipe.set("a", "1", ex=10)
                pipe.incr("counter")
                results: list[object] = await pipe.execute()
        """
        pipe = self.require_client().pipeline(transaction=transaction)
        try:
            yield pipe
        finally:
            await pipe.reset()

    # -------------------------------------------------------------- #
    # locks (SET NX + TTL)
    # -------------------------------------------------------------- #

    async def acquire_lock(self, key: Key, ttl: TTL = 10) -> bool:
        return await self.set(f"lock:{key}", "1", ttl=ttl, nx=True)

    async def release_lock(self, key: Key) -> bool:
        return bool(await self.delete(f"lock:{key}"))

    @asynccontextmanager
    async def lock(self, key: Key, ttl: TTL = 10) -> AsyncIterator[bool]:
        acquired = await self.acquire_lock(key, ttl)
        try:
            yield acquired
        finally:
            if acquired:
                await self.release_lock(key)