"""Политики повторов для сетевых операций."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from app.drivers.exceptions import RedisConnectionFailure, RedisDriverError, RedisTimeout

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Конфигурация экспоненциального backoff."""

    attempts: int = 3
    base_delay: float = 0.05
    max_delay: float = 1.0
    jitter: float = 0.25
    retry_on: tuple[type[RedisDriverError], ...] = (
        RedisConnectionFailure,
        RedisTimeout,
    )

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be >= 1")
        if self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("invalid delay bounds")

    def delay(self, attempt: int) -> float:
        raw = min(self.max_delay, self.base_delay * (2 ** attempt))
        return raw + random.uniform(0, self.jitter * raw)


async def run_with_retry(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig,
) -> T:
    """Выполнить `fn()` с ретраями согласно `config`."""
    last: RedisDriverError | None = None
    for attempt in range(config.attempts):
        try:
            return await fn()
        except config.retry_on as exc:
            last = exc
            if attempt == config.attempts - 1:
                break
            await asyncio.sleep(config.delay(attempt))
    assert last is not None
    raise last