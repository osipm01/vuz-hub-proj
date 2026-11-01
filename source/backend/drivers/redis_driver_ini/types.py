"""Типы и протоколы, используемые драйвером."""

from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    Final,
    Literal,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# Значения, которые можно записать в Redis как строка
RedisValue = str | bytes | int | float

# Результат сырого GET (bytes или str в зависимости от decode_responses)
RawValue = str | bytes | None

# TTL в секундах
TTL = int

# Команда/ключ
Key = str

# JSON-совместимый тип
JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_json = TypeVar("T_json", bound=JsonValue)

# Политика повторов
RetryPolicy = Literal["none", "connect", "all"]

# Pipeline-команды, ожидающие Awaitable
PipelineCommand = Callable[[], Awaitable[Any]]


@runtime_checkable
class Lock(Protocol):
    """Интерфейс распределённой блокировки."""

    acquired: bool

    async def release(self) -> bool: ...
    async def extend(self, ttl: TTL) -> bool: ...


__all__ = [
    "RedisValue",
    "RawValue",
    "TTL",
    "Key",
    "JsonValue",
    "T",
    "T_co",
    "T_json",
    "RetryPolicy",
    "PipelineCommand",
    "Lock",
]