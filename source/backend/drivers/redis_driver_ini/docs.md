# `docs.md`

```markdown
# Redis Driver

Асинхронный Redis-драйвер для Python с строгой типизацией, иерархией исключений и опциональными ретраями. Предназначен для использования в CRUD-слоях и сервисах.

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [Конфигурация](#конфигурация)
- [Жизненный цикл](#жизненный-цикл)
- [Ключи и префиксы](#ключи-и-префиксы)
- [API](#api)
  - [Утилиты](#утилиты)
  - [Strings](#strings)
  - [Счётчики](#счётчики)
  - [JSON](#json)
  - [Hashes](#hashes)
  - [Lists](#lists)
  - [Sets](#sets)
  - [Sorted Sets](#sorted-sets)
  - [Pipeline](#pipeline)
  - [Блокировки](#блокировки)
- [Обработка ошибок](#обработка-ошибок)
- [Ретраи](#ретраи)
- [Типы](#типы)
- [Интеграция с FastAPI](#интеграция-с-fastapi)
- [Примеры сервисов](#примеры-сервисов)
- [Чек-лист для продакшена](#чек-лист-для-продакшена)

---

## Установка

```bash
pip install redis
```

Минимальная версия `redis-py`: **5.x** (используется `redis.asyncio`).

---

## Быстрый старт

```python
import asyncio

from app.drivers.redis_driver import RedisDriver


async def main() -> None:
    async with RedisDriver(url="redis://localhost:6379/0", key_prefix="app:") as redis:
        await redis.set("greeting", "hello", ttl=60)
        value = await redis.get("greeting")
        print(value)  # "hello"


asyncio.run(main())
```

---

## Архитектура

```
app/
├── drivers/
│   ├── __init__.py
│   ├── redis_driver.py     # RedisDriver — основной класс
│   ├── exceptions.py       # иерархия исключений + translate()
│   ├── retry.py            # RetryConfig, run_with_retry()
│   └── types.py            # псевдонимы типов (JsonValue, RedisValue, ...)
├── config/
│   └── settings.py         # настройки через pydantic-settings
└── services/               # CRUD/сервисы, использующие драйвер
```

**Слои:**

```
┌─────────────────────────────┐
│  Service / CRUD layer       │  UserCacheService, RateLimiter, ...
├─────────────────────────────┤
│  RedisDriver                │  типизированный фасад над redis-py
├─────────────────────────────┤
│  redis.asyncio.Redis        │  пул соединений
└─────────────────────────────┘
```

Драйвер **не знает** о доменных моделях. Всё, что нужно сервису — вызвать `driver.<method>()` и получить предсказуемый тип.

---

## Конфигурация

```python
RedisDriver(
    url="redis://localhost:6379/0",   # DSN
    decode_responses=True,             # str вместо bytes
    max_connections=20,                # размер пула
    socket_timeout=5.0,                # таймаут операций
    socket_connect_timeout=5.0,        # таймаут коннекта
    health_check_interval=30,          # проверка мёртвых соединений
    key_prefix="app:",                 # namespacing
    retry=RetryConfig(attempts=3),     # опционально
)
```

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `url` | `str` | `redis://localhost:6379/0` | DSN подключения |
| `decode_responses` | `bool` | `True` | Декодировать байты в `str` |
| `max_connections` | `int` | `20` | Размер пула соединений |
| `socket_timeout` | `float` | `5.0` | Таймаут операции (сек) |
| `socket_connect_timeout` | `float` | `5.0` | Таймаут подключения (сек) |
| `health_check_interval` | `int` | `30` | Периодичность health-check |
| `key_prefix` | `str` | `""` | Префикс всех ключей |
| `retry` | `RetryConfig \| None` | `None` | Политика ретраев |

**Валидация при инициализации:**

- `max_connections >= 1`
- `socket_timeout > 0`, `socket_connect_timeout > 0`

Настройки через окружение (`pydantic-settings`):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    redis_key_prefix: str = "app:"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

`.env`:

```env
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20
REDIS_KEY_PREFIX=app:
```

---

## Жизненный цикл

```python
# Вариант 1: контекстный менеджер (рекомендуется)
async with RedisDriver(url=...) as redis:
    ...

# Вариант 2: вручную
redis = RedisDriver(url=...)
await redis.connect()
try:
    ...
finally:
    await redis.close()
```

- `connect()` — создаёт пул и **пингует** Redis. При ошибке клиент закрывается, а исключение транслируется в `RedisConnectionFailure`.
- `close()` — идемпотентен, `client` обнуляется.
- Если методы вызываются до `connect()` — поднимается `RedisNotInitialized`.

---

## Ключи и префиксы

Если задан `key_prefix`:

| Что делаете | Что видит Redis |
|---|---|
| `redis.set("user:1", ...)` | ключ `app:user:1` |
| `redis.keys("user:*")` | сканирует `app:user:*`, возвращает `["user:1", ...]` |
| `redis.scan_iter("user:*")` | то же, лениво |

Префикс применяется **автоматически** ко всем методам, работающим с ключами. Снимать префикс вручную не нужно.

> ⚠️ `keys()` использует `KEYS` и блокирует Redis. В продакшене предпочитайте `scan_iter()`.

---

## API

### Утилиты

```python
await redis.ping() -> bool                     # health check, не бросает исключений
await redis.exists(key) -> bool
await redis.delete(*keys) -> int               # кол-во удалённых
await redis.expire(key, seconds) -> bool
await redis.ttl(key) -> int                    # -1 нет TTL, -2 нет ключа
await redis.keys(pattern="*") -> list[str]
async for k in redis.scan_iter(pattern="*"):   # ленивая итерация
    ...
```

### Strings

```python
await redis.get(key) -> str | bytes | None
await redis.set(key, value, *, ttl=None, nx=False, xx=False) -> bool
await redis.getset(key, value) -> str | bytes | None
await redis.mget(*keys) -> list[str | bytes | None]
await redis.mset({k: v, ...}) -> bool
```

Правила:

- `ttl <= 0` → `ValueError`
- `nx=True` и `xx=True` одновременно → `ValueError`
- `set(...)` возвращает `False`, если `nx=True` и ключ уже существует, или `xx=True` и ключа нет

### Счётчики

```python
await redis.incr(key, amount=1) -> int
await redis.decr(key, amount=1) -> int
```

### JSON

```python
await redis.set_json(key, value, *, ttl=None) -> bool
await redis.get_json(key) -> JsonValue | None
```

- `value` — любой JSON-совместимый объект (dict, list, str, int, float, bool, None)
- ошибка кодирования → `RedisSerializationError`
- битый JSON в Redis → `RedisSerializationError`

### Hashes

```python
await redis.hset(key, mapping) -> int
await redis.hget(key, field) -> str | bytes | None
await redis.hgetall(key) -> dict[str, str]
await redis.hdel(key, *fields) -> int
await redis.hexists(key, field) -> bool
await redis.hincrby(key, field, amount=1) -> int
```

### Lists

```python
await redis.lpush(key, *values) -> int
await redis.rpush(key, *values) -> int
await redis.lrange(key, start=0, end=-1) -> list[str]
await redis.lpop(key) -> str | bytes | None
await redis.rpop(key) -> str | bytes | None
await redis.llen(key) -> int
await redis.ltrim(key, start, end) -> bool
```

### Sets

```python
await redis.sadd(key, *members) -> int
await redis.smembers(key) -> set[str]
await redis.srem(key, *members) -> int
await redis.sismember(key, member) -> bool
```

### Sorted Sets

```python
await redis.zadd(key, {member: score, ...}) -> int
await redis.zrange(key, start=0, end=-1, *, withscores=False, desc=False)
    -> list[str] | list[tuple[str, float]]
await redis.zrem(key, *members) -> int
await redis.zincrby(key, member, amount=1.0) -> float
```

### Pipeline

```python
async with redis.pipeline(transaction=True) as pipe:
    pipe.set("a", "1", ex=10)
    pipe.incr("counter")
    pipe.hset("meta", mapping={"role": "admin"})
    results: list[object] = await pipe.execute()
```

- `transaction=True` — `MULTI/EXEC` (атомарно)
- `transaction=False` — просто batch (без транзакции)
- `pipe.reset()` вызывается автоматически при выходе из контекста

### Блокировки

Реализованы через `SET key value NX EX ttl`.

```python
# Низкоуровневый API
acquired: bool = await redis.acquire_lock("cron", ttl=10)
released: bool = await redis.release_lock("cron")

# Контекстный менеджер
async with redis.lock("cron", ttl=10) as acquired:
    if acquired:
        ...  # критическая секция
```

> ⚠️ Это **не** Redlock. Для критичных сценариев используйте `redlock-py` или `aioredlock`.

---

## Обработка ошибок

Все ошибки наследуются от `RedisDriverError`. `redis-py`-исключения **транслируются** с сохранением `__cause__`.

```
RedisDriverError
├── RedisConnectionFailure     # сеть, обрыв соединения
├── RedisTimeout               # таймаут операции
├── RedisOperationFailure      # Redis вернул ошибку (WRONGTYPE, ...)
├── RedisDataFailure           # некорректные данные
│   └── RedisSerializationError   # ошибки JSON
└── RedisNotInitialized        # драйвер не подключён
```

Пример:

```python
from app.drivers.exceptions import (
    RedisConnectionFailure,
    RedisDriverError,
    RedisSerializationError,
)

try:
    user = await redis.get_json("user:1")
except RedisSerializationError as exc:
    log.error("corrupted payload: %s", exc)
except RedisConnectionFailure as exc:
    log.error("redis down: %s", exc)
except RedisDriverError as exc:
    log.error("redis error: %s", exc)
```

Трансляция:

| redis-py | драйвер |
|---|---|
| `ConnectionError` | `RedisConnectionFailure` |
| `TimeoutError` | `RedisTimeout` |
| `DataError` | `RedisDataFailure` |
| `ResponseError` | `RedisOperationFailure` |
| прочие `RedisError` | `RedisOperationFailure` |

---

## Ретраи

По умолчанию ретраев нет. Включаются передачей `RetryConfig`.

```python
from app.drivers.redis_driver import RedisDriver
from app.drivers.retry import RetryConfig

redis = RedisDriver(
    url="redis://...",
    retry=RetryConfig(
        attempts=3,
        base_delay=0.05,
        max_delay=1.0,
        jitter=0.25,
    ),
)
```

| Параметр | По умолчанию | Описание |
|---|---|---|
| `attempts` | `3` | Всего попыток (включая первую) |
| `base_delay` | `0.05` | Базовая задержка (сек) |
| `max_delay` | `1.0` | Максимальная задержка (сек) |
| `jitter` | `0.25` | Доля случайной добавки (0..1) |
| `retry_on` | `(ConnectionFailure, Timeout)` | Какие ошибки повторять |

Задержка: `min(max_delay, base_delay * 2^attempt) + uniform(0, jitter * delay)`.

**Не ретраятся** ошибки логического уровня: `RedisOperationFailure`, `RedisSerializationError`.

---

## Типы

Из `app.drivers.types`:

```python
RedisValue = str | bytes | int | float      # что можно записать
RawValue = str | bytes | None               # сырой GET
TTL = int                                   # секунды
Key = str
JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
RetryPolicy = Literal["none", "connect", "all"]  # задел на будущее
```

Псевдонимы помогают держать сигнатуры читаемыми и ловят ошибки при `mypy --strict`.

---

## Интеграция с FastAPI

```python
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request

from app.config.settings import settings
from app.drivers.redis_driver import RedisDriver


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = RedisDriver(
        url=settings.redis_url,
        key_prefix=settings.redis_key_prefix,
        max_connections=settings.redis_max_connections,
    )
    await redis.connect()
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.close()


app = FastAPI(lifespan=lifespan)


def get_redis(request: Request) -> RedisDriver:
    return request.app.state.redis


RedisDep = Annotated[RedisDriver, Depends(get_redis)]


@app.get("/health")
async def health(redis: RedisDep) -> dict[str, bool]:
    return {"redis": await redis.ping()}
```

**Правила для эндпоинтов:**

1. Один `RedisDriver` на приложение — не создавайте на каждый запрос.
2. Не храните состояние в `app.state.redis` — драйвер stateless после `connect()`.
3. `health` через `ping()`, а не `GET`.

---

## Примеры сервисов

### Кэш (cache-aside)

```python
from typing import Awaitable, Callable

from app.drivers.redis_driver import RedisDriver
from app.drivers.types import JsonValue

UserDict = dict[str, JsonValue]
UserLoader = Callable[[int], Awaitable[UserDict | None]]


class UserCacheService:
    __slots__ = ("redis", "ttl")

    def __init__(self, redis: RedisDriver, ttl: int = 300) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.redis = redis
        self.ttl = ttl

    def key(self, user_id: int) -> str:
        return f"user:{user_id}"

    async def get(self, user_id: int) -> UserDict | None:
        data = await self.redis.get_json(self.key(user_id))
        if not isinstance(data, dict):
            return None
        return {str(k): v for k, v in data.items()}

    async def set(self, user: UserDict) -> None:
        user_id = user.get("id")
        if not isinstance(user_id, int):
            raise ValueError("user must contain integer 'id'")
        await self.redis.set_json(self.key(user_id), user, ttl=self.ttl)

    async def invalidate(self, user_id: int) -> None:
        await self.redis.delete(self.key(user_id))

    async def remember(self, user_id: int, loader: UserLoader) -> UserDict | None:
        cached = await self.get(user_id)
        if cached is not None:
            return cached
        user = await loader(user_id)
        if user is not None:
            await self.set(user)
        return user
```

### Rate limiter (fixed window)

```python
class RateLimiter:
    __slots__ = ("redis",)

    def __init__(self, redis: RedisDriver) -> None:
        self.redis = redis

    async def hit(self, identifier: str, limit: int, window: int) -> bool:
        if limit <= 0 or window <= 0:
            raise ValueError("limit and window must be positive")
        key = f"rl:{identifier}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, window)
        return count <= limit
```

### Инвалидация по тегу

```python
class TagIndex:
    __slots__ = ("redis",)

    def __init__(self, redis: RedisDriver) -> None:
        self.redis = redis

    async def add(self, tag: str, key: str) -> None:
        await self.redis.sadd(f"index:{tag}", key)

    async def members(self, tag: str) -> set[str]:
        return await self.redis.smembers(f"index:{tag}")

    async def invalidate(self, tag: str) -> int:
        members = await self.members(tag)
        if not members:
            return 0
        return await self.redis.delete(*members)
```

---

## Чек-лист для продакшена

- [ ] `key_prefix` уникален для сервиса (например, `billing:`, `auth:`).
- [ ] `max_connections` согласован с пулом воркеров (`workers * max_connections <= maxclients` в `redis.conf`).
- [ ] `socket_timeout` **меньше** таймаута запроса на уровне API.
- [ ] `decode_responses=True` (иначе все методы вернут `bytes`).
- [ ] `RetryConfig` включён для сетевых вызовов в критичных путях.
- [ ] `scan_iter` вместо `keys` для больших пространств ключей.
- [ ] Для блокировок — отдельная библиотека (Redlock), а не `SET NX`.
- [ ] Логи не содержат пароль из `url` (драйвер сам не логирует DSN — проверьте свой код).
- [ ] `ping()` в `/health` эндпоинте.
- [ ] Метрики: количество ошибок по типам, latency `ping()`.
```

Если нужно — добавлю **раздел про pub/sub**, **Redis Streams**, **кластерный режим** или **миграцию с `redis-py` напрямую**.