Ниже — переписанная документация под текущее состояние проекта: новая модель `User` (с `role`, соц-сетями), `UserRole`, `UserCRUD`/`UserService` как модульные синглтоны (без `__new__`/`_initialized`), JWT-токены с `HMAC`-ключом, `role_guard` с `Principal`, обновлённый роутер `/users` и `data_validation`.

---

# 📚 Документация проекта VuzHub

> Документация отражает **актуальное состояние** проекта после рефакторинга: модульные синглтоны, `UserRole`, JWT-токены с проверяемым `key`, `role_guard` на `Principal`, соц-привязки.

---

## 🗂 Структура проекта

```
project/
├── core/
│   ├── config.py              # Настройки проекта (Settings)
│   └── database.py            # Асинхронная сессия БД
├── enums/
│   ├── auth_type_enum.py      # AuthType: CLIENT / BOT / INTEGRATION
│   └── user_enums.py          # SocialNetworkLinkType, UserRole
├── interfaces/
│   ├── auth_headers.py        # Имена заголовков авторизации
│   └── token_paylod.py        # TokenPayload (TypedDict для client JWT)
├── models/                    # SQLAlchemy модели
├── schemas/                   # Pydantic DTO
├── crud/                      # CRUD-классы (модульные синглтоны)
├── services/                  # Бизнес-логика (модульные синглтоны)
├── api/                       # Роутеры FastAPI
├── data_validation.py         # Генерация/валидация integration & bot JWT
├── role_guard.py              # Principal, get_principal, role_guard
└── main.py                    # Сборка приложения
```

---

## ⚙️ core/config — Настройки проекта

### Расположение
`core/config.py` — настройки заданы в Python-классе; `SettingsConfigDict(env_file=".env", ...)` уже присутствует, так что при появлении `.env` значения подхватятся автоматически.

### Класс `Settings`

| Параметр | Тип | Значение по умолчанию | Назначение |
|---|---|---|---|
| `SECRET_JWT_KEY` | `str` | `qwert` | Секрет для JWT (client + service) и HMAC `key` |
| `ALGORITHM` | `str` | `HS256` | Алгоритм JWT |
| `ACCESS_TOKEN_COOKIE_NAME` | `str` | `access_token` | Cookie с client-токеном |
| `DB_HOST` | `str` | `localhost` | Хост PostgreSQL |
| `DB_PORT` | `int` | `5432` | Порт PostgreSQL |
| `DB_USER` | `str` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `str` | `admin` | Пароль БД |
| `DB_NAME` | `str` | `vuxhubbd` | Имя базы данных |

### Свойство `DATABASE_URL`

```python
@property
def DATABASE_URL(self) -> str:
    return (
        f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
        f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    )
```

DSN для драйвера `asyncpg`.

### Использование

```python
from core.config import settings
print(settings.DATABASE_URL)
# postgresql+asyncpg://postgres:admin@localhost:5432/vuxhubbd
```

> ⚠️ `SECRET_JWT_KEY = "qwert"` — дефолт; перед продакшеном заменить и держать в `.env` / vault.

---

## 🗄 core/database — Асинхронная сессия БД

| Объект | Тип | Назначение |
|---|---|---|
| `engine` | `AsyncEngine` | Асинхронный движок SQLAlchemy |
| `AsyncSessionLocal` | `async_sessionmaker[AsyncSession]` | Фабрика сессий |
| `Base` | `DeclarativeBase` | Базовый класс ORM-моделей |
| `get_async_db` | `AsyncGenerator[AsyncSession]` | FastAPI dependency |

### Правила
- **Одна сессия на HTTP-запрос** — через `Depends(get_async_db)`.
- `commit()` — в CRUD/service слое.
- `rollback()` — на ошибках (см. `UserCRUD`: `IntegrityError` / `SQLAlchemyError` / `Exception`).
- `pool_pre_ping=True`.

---

## 🧱 models — ORM-модели

- Наследуются от `Base`.
- `__tablename__` — snake_case, множественное число.
- `id` (PK), `created_at` (`server_default=func.now()`).

### `User` (актуальная модель)

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        String, nullable=False, default=UserRole.USER
    )

    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    VK_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    MAX_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)

    group: Mapped[Optional["Group"]] = relationship(back_populates="users")
    debts: Mapped[List["Debt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_subjects: Mapped[List["UserSubject"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    dops: Mapped[List["Dop"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
```

> `role` — `String` + `UserRole(str, Enum)`. Роль хранится строкой, типизируется enum'ом.

---

## 🔣 enums — перечисления

### `enums/auth_type_enum.py`

```python
class AuthType(str, Enum):
    CLIENT = "client"          # user (JWT в cookie / x-auth-token / Authorization)
    BOT = "bot"                # x-bot-token
    INTEGRATION = "integration"# x-integration-key
```

### `enums/user_enums.py`

```python
class SocialNetworkLinkType(str, Enum):
    VK = "vk"
    MAX_id = "max_id"
    TG_ID = "tg_id"

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MANAGER = "manager"
```

`str`-enum: `UserRole.ADMIN == "admin"` → `True`, поэтому сравнение с `payload["role"]` из JWT работает без преобразований.

---

## 🔐 JWT: client, integration, bot

Проект использует **три вида токенов**:

| Вид | Заголовок | Кто создаёт | Где проверяется |
|---|---|---|---|
| `client` (user) | cookie `access_token` / `x-auth-token` / `Authorization: Bearer` | auth-сервис | `role_guard.decode_jwt` (стандартный `exp`) |
| `integration` | `x-integration-key` | `data_validation.generate_integration_token` | `data_validation.validation_integration_token` |
| `bot` | `x-bot-token` | `data_validation.generate_bot_token` | `data_validation.validation_bot_token` |

Тип выбирается заголовком **`x-auth-type`** (`client` | `bot` | `integration`); отсутствует → `client`.

### `data_validation.py` — service-токены

Модели payload (frozen dataclasses):

```python
@dataclass(frozen=True, slots=True)
class IntegrationTokenPayload:
    issued_at: int          # unix ts
    expires_at: int         # -1 = бессрочно
    key: str                # HMAC-SHA256(issued_at, SECRET)
    token_type: Literal["integration"]
    integration_id: str
    scopes: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class BotTokenPayload:
    issued_at: int
    expires_at: int
    key: str
    token_type: Literal["bot"]
    bot_id: str
    permissions: tuple[str, ...] = ()
```

Ключ — **HMAC-SHA256 от даты выдачи** с секретом:

```python
def _make_key(issued_at: int) -> str:
    return hmac.new(_SECRET, str(issued_at).encode(), hashlib.sha256).hexdigest()
```

Детерминированно и проверяемо при валидации (`hmac.compare_digest`), без БД.

Генерация:

```python
def generate_integration_token(*, integration_id: str,
                               scopes: Sequence[str] = (),
                               ttl_seconds: int = -1) -> str: ...
def generate_bot_token(*, bot_id: str,
                       permissions: Sequence[str] = (),
                       ttl_seconds: int = -1) -> str: ...
```

- `ttl_seconds = -1` → `expires_at = -1` (бессрочно).
- JWT кодируется `jwt.encode(asdict(payload), SECRET, algorithm=ALGORITHM)`.
- Декодирование — `verify_exp=False` (свой `expires_at`).

Валидация (`validation_integration_token` / `validation_bot_token`) проверяет:
1. подпись и формат JWT;
2. `token_type` соответствует ожидаемому;
3. `issued_at` / `expires_at` — `int`;
4. `key == HMAC(issued_at)` (timing-safe);
5. `expires_at == -1 or now <= expires_at`;
6. обязательные поля (`integration_id` / `bot_id`), типы `scopes` / `permissions`.

При ошибке — `None` + лог (`INFO` — истёк/неверный тип; `WARNING` — невалидная подпись/key/поля). Токен и `key` **не логируются**.

---

## 🛡 role_guard.py — аутентификация и авторизация

### `Principal`

```python
@dataclass(frozen=True, slots=True)
class Principal:
    kind: Literal["user", "bot", "integration"]
    role: UserRole | None = None
    user_id: int | None = None            # из JWT sub (если число)
    bot: BotTokenPayload | None = None
    integration: IntegrationTokenPayload | None = None
```

### `get_principal`

FastAPI dependency:
1. `extract_auth_type(request)` — по `x-auth-type` (по умолчанию `CLIENT`).
2. `BOT` → `x-bot-token` → `validation_bot_token` → `Principal(kind="bot", bot=...)`.
3. `INTEGRATION` → `x-integration-key` → `validation_integration_token` → `Principal(kind="integration", integration=...)`.
4. `CLIENT` → cookie `access_token` / `x-auth-token` / `Authorization` → `decode_jwt` → `role = UserRole(payload["role"])`, `user_id = int(payload["sub"])` → `Principal(kind="user", role, user_id)`.

Ошибки → `401` (`unauthorized`), с `WWW-Authenticate: Bearer`.

### `role_guard(allowed_roles, allowed_kinds)`

```python
def role_guard(
    allowed_roles: Sequence[UserRole],
    allowed_kinds: set[AuthType],
) -> Callable[..., Coroutine[Any, Any, Principal]]: ...
```

Семантика:
- **user** — `role ∈ allowed_roles` **и** `AuthType.CLIENT ∈ allowed_kinds`, иначе `403`;
- **bot / integration** — роли нет; доступ только если их kind явно указан в `allowed_kinds`, иначе `403`.

Примеры:

```python
role_guard([UserRole.ADMIN], {AuthType.CLIENT})                 # только админ
role_guard([UserRole.ADMIN], {AuthType.CLIENT, AuthType.BOT})   # админ или любой валидный bot
role_guard([], {AuthType.BOT, AuthType.INTEGRATION})            # только сервисы
```

### Обратная совместимость

`get_token`, `decode_jwt`, `get_current_role` сохранены. `get_current_role` возвращает `UserRole` и объявлен **после** `get_token` (иначе `Depends(get_token)` даст `Unresolved reference`).

---

## 📦 schemas — DTO (Pydantic)

Разделение: `Create` / `Update` / `Read` / служебные. `Read`-схемы — `ConfigDict(from_attributes=True)`.

### `schemas/user_schema.py`

| Схема | Назначение |
|---|---|
| `UserBase` | `name`, `email`, `group_id` |
| `UserCreate(UserBase)` | создание; **роль не передаётся** (назначает сервис, по умолчанию `USER`) |
| `UserUpdate` | частичное обновление профиля; роль **не меняется** |
| `UserRoleUpdate` | `{"role": UserRole}` — отдельный админский payload смены роли |
| `UserRead` | `id`, `name`, `email`, `group_id`, `role: UserRole`, `created_at` |
| `SocialLinkInfo` | `link_type`, `social_id: int \| None` |
| `SocialLinksResponse` | `user_id`, `links: list[SocialLinkInfo]` |
| `SocialLinkRequest` | `link_type`, `social_id: int` (`gt=0`) |
| `SocialUnlinkRequest` | `link_type` |
| `SocialAuthRequest` / `SocialAuthResponse` | вход/регистрация через соцсеть |
| `SocialLinksPatch` / `SocialLinksPatchResult` | массовое обновление привязок |

Помощник `build_social_links(user) -> SocialLinksResponse` собирает привязки из ORM-объекта.

> `social_id` везде `int` (в модели `BigInteger`/`Integer`), без `Union[int, str]`.

---

## 🔁 crud — CRUD-классы (модульные синглтоны)

### Требования
- Один экземпляр на приложение — **модульный синглтон** (`user_crud = UserCRUD()`), без `__new__`/`_initialized`.
- Только атомарные операции с БД, без бизнес-логики.
- Сессия передаётся параметром, **не хранится** в классе.

### `UserCRUD` (актуальный API)

```python
class UserCRUD:
    def __init__(self) -> None:
        self.social_field_map: Final[dict[SocialNetworkLinkType, str]] = _SOCIAL_FIELD_MAP

    def get_social_field(self, link_type: SocialNetworkLinkType) -> str: ...

    async def create_user(self, db, data: UserCreate,
                          role: UserRole = UserRole.USER) -> User: ...
    async def get_user(self, db, user_id: int) -> User | None: ...
    async def get_user_by_email(self, db, email: str) -> User | None: ...
    async def get_user_by_social(self, db,
                                 link_type: SocialNetworkLinkType,
                                 social_id: int) -> User | None: ...
    async def get_user_with_relations(self, db, user_id: int) -> User | None: ...
    async def get_users(self, db, skip=0, limit=100,
                        group_id: int | None = None) -> Sequence[User]: ...

    async def update_user(self, db, user: User, data: UserUpdate) -> User: ...
    async def update_role(self, db, user: User, role: UserRole) -> User: ...

    async def link_social(self, db, user, link_type, social_id: int) -> User: ...
    async def unlink_social(self, db, user, link_type) -> User: ...

    async def get_user_by_telegram_id(self, db, telegram_id: int) -> User | None: ...
    async def get_user_by_vk_id(self, db, vk_id: int) -> User | None: ...
    async def get_user_by_max_id(self, db, max_id: int) -> User | None: ...

    async def delete_user(self, db, user: User) -> bool: ...


user_crud: Final[UserCRUD] = UserCRUD()
```

Особенности:
- `create_user(..., role=UserRole.USER)` — роль назначается здесь, не из DTO.
- `update_role` — отдельный метод (не через `UserUpdate`), логирует `old -> new`.
- Все `commit/refresh` обёрнуты: `IntegrityError` → `ValueError` (для сервиса), `SQLAlchemyError` / `Exception` → `logger.exception` + re-raise.
- Публичные `social_field_map` / `get_social_field` — без ведущего `_`.

---

## 🧠 services — Бизнес-логика (модульные синглтоны)

- Тот же паттерн: `user_service: Final[UserService] = UserService()`.
- Инкапсулируют правила домена: проверка уникальности email, оркестрация CRUD, `HTTPException`.
- `self.crud: Final = user_crud`.

### `UserService` (актуальный API)

```python
async def create_user(self, db, data: UserCreate,
                      role: UserRole = UserRole.USER) -> User: ...
async def get_user_or_404(self, db, user_id: int) -> User: ...
async def get_user_by_email_or_404(self, db, email: str) -> User: ...
async def get_user_with_relations_or_404(self, db, user_id: int) -> User: ...
async def list_users(self, db, skip=0, limit=100,
                     group_id: int | None = None) -> Sequence[User]: ...
async def get_user_by_social_or_404(self, db, link_type, social_id: int) -> User: ...

async def update_user(self, db, user_id: int, data: UserUpdate) -> User: ...
async def update_role(self, db, user_id: int, role: UserRole) -> User: ...

async def link_social(self, db, user_id, link_type, social_id: int) -> User: ...
async def unlink_social(self, db, user_id, link_type) -> User: ...
async def delete_user(self, db, user_id: int) -> None: ...
```

Особенности:
- `update_role` — no-op при той же роли (`logger.info("no-op ...")`).
- `unlink_social` проверяет наличие привязки через публичный `crud.get_social_field` → `400`, если привязки нет.
- `link_social` предварительно проверяет занятость `social_id` → `409` до вставки.
- Все CRUD-исключения маппятся в `HTTPException` (`400/404/409`).

---

## 🌐 api — Эндпоинты FastAPI

### Правила
- `APIRouter(prefix="/users", tags=["users"])`, регистрация через `include_router` в `main.py`.
- БД — `Annotated[AsyncSession, Depends(get_async_db)]`.
- Авторизация — `Depends(get_principal)` / `Depends(role_guard(...))`.
- Ответы — `UserRead.model_validate(user)`.

### Зависимости (готовые алиасы)

```python
DbSession = Annotated[AsyncSession, Depends(get_async_db)]
AdminOnly = Annotated[Principal, Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))]
AnyAuth   = Annotated[Principal, Depends(get_principal)]
```

### Роутер пользователей (`api/users_router.py`)

| Метод | Путь | Auth | Тело / Path | Ответ | Описание |
|---|---|---|---|---|---|
| `GET` | `/users/me` | any user | — | `UserRead` | Текущий пользователь (из `Principal.user_id`) |
| `GET` | `/users` | `ADMIN` | `skip`, `limit`, `group_id` | `list[UserRead]` | Список |
| `GET` | `/users/by-email` | `ADMIN` | `email` | `UserRead` | По email |
| `GET` | `/users/{user_id}` | `ADMIN` | `user_id` | `UserRead` | По ID (со связями) |
| `POST` | `/users` | `ADMIN` | `UserCreate` | `UserRead` (201) | Создать |
| `PUT` | `/users/{user_id}` | `ADMIN` | `UserUpdate` | `UserRead` | Обновить профиль |
| `PATCH` | `/users/{user_id}/role` | `ADMIN` | `UserRoleUpdate` | `UserRead` | Сменить роль |
| `DELETE` | `/users/{user_id}` | `ADMIN` | — | `204` | Удалить |
| `GET` | `/users/{user_id}/social` | `ADMIN` | — | `SocialLinksResponse` | Привязки |
| `POST` | `/users/{user_id}/social/link` | `ADMIN` | `SocialLinkRequest` | `UserRead` | Привязать |
| `POST` | `/users/{user_id}/social/unlink` | `ADMIN` | `query link_type` | `UserRead` | Отвязать |

Ключевые фрагменты:

```python
@router.get("/me", response_model=UserRead, summary="Текущий пользователь")
async def get_me(principal: AnyAuth, db: DbSession) -> UserRead:
    if principal.kind != "user" or principal.user_id is None:
        raise HTTPException(403, "Эндпоинт доступен только пользователям")
    user = await user_service.get_user_or_404(db, principal.user_id)
    return UserRead.model_validate(user)

@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def update_user_role(data: UserRoleUpdate, db: DbSession,
                           user_id: int = Path(..., gt=0)) -> UserRead:
    user = await user_service.update_role(db, user_id, data.role)
    return UserRead.model_validate(user)
```

> Сервисные эндпоинты (bot/integration) защищаются `role_guard([], {AuthType.BOT, AuthType.INTEGRATION})` — роли им не нужны.

---

## 🧭 Правила слоёв

```
api  →  services  →  crud  →  models
         (логика)   (singleton)  (ORM)
              ↑
           schemas (DTO)
```

1. **api** — валидация входа/выхода, вызов сервиса. Никаких SQL-запросов.
2. **services** — бизнес-правила, транзакции, вызов нескольких CRUD, `HTTPException`.
3. **crud** — атомарные операции с БД, модульный синглтон.
4. **models** — только описание таблиц.
5. **schemas** — только контракты API.

### Запрещено
- Импортировать `models` напрямую в `api`.
- Импортировать `crud` напрямую в `api` (только через `services`).
- Хранить `AsyncSession` в синглтон-классах — сессия передаётся параметром.
- Использовать `__new__`/`_initialized` для синглтонов — только модульный экземпляр.
- Логировать JWT, `key`, пароли.

---

## 🚀 Запуск

```bash
uvicorn main:app --reload
```

- Swagger UI → `http://localhost:8000/docs`

---

## 📝 Заметки о текущем состоянии

- **Синглтоны** — модульные (`user_crud`, `user_service`), без метаклассов и `__new__`.
- **`User.role`** — `String` + `UserRole(str, Enum)`, дефолт `UserRole.USER`; меняется только через `UserService.update_role` (админский `PATCH /users/{id}/role`).
- **`data_validation`** — `key = HMAC-SHA256(issued_at, SECRET)`, проверяется при валидации (timing-safe). `expires_at = -1` = бессрочно.
- **`role_guard`** — `Principal(kind, role, user_id, bot, integration)`; `allowed_kinds: set[AuthType]`; bot/integration не имеют роли и допускаются только при явном указании их kind.
- **`social_id`** — везде `int` (`gt=0`); привязки через тело (`SocialLinkRequest`), а не path.
- **`SECRET_JWT_KEY = "qwert"`** — дефолт; заменить перед продакшеном.
- **`.env`** — `SettingsConfigDict` готов, файла пока нет; значения из дефолтов.
- **`get_current_role`** — совместимость; объявлен после `get_token`, чтобы `Depends(get_token)` резолвился.