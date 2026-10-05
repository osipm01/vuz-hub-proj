# 📚 Документация проекта VuxHub

> Ниже — документация **по уже реализованному проекту**.  
> Конфиг на текущий момент хранится прямо в `.py`-файле (`core/config.py`) без использования `.env`.

---

## 🗂 Структура проекта

```
project/
├── core/
│   ├── config.py          # Настройки проекта (Settings) — в .py-файле
│   └── database.py        # Асинхронная сессия БД
├── models/                # SQLAlchemy модели
├── schemas/               # Pydantic DTO
├── crud/                  # CRUD-классы (строго Singleton)
├── services/              # Бизнес-логика (Singleton, аналогично CRUD)
└── api/                   # Эндпоинты (роутеры FastAPI)
```

---

## ⚙️ core/config — Настройки проекта

### Расположение
`core/config.py` — настройки заданы **прямо в Python-классе**, `.env` пока не используется.

### Класс `Settings`

| Параметр | Тип | Значение по умолчанию | Назначение |
|---|---|---|---|
| `AUTH_CHECK_URL` | `str` | `https://localhost:3100/api/users/check-auth-by-token` | URL сервиса проверки авторизации по токену |
| `SECRET_JWT_KEY` | `str` | `qwert` | Секретный ключ для JWT |
| `DB_HOST` | `str` | `localhost` | Хост PostgreSQL |
| `DB_PORT` | `int` | `5432` | Порт PostgreSQL |
| `DB_USER` | `str` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `str` | `admin` | Пароль БД |
| `DB_NAME` | `str` | `vuxhubbd` | Имя базы данных |

### Свойство `DATABASE_URL`

```python
@property
def DATABASE_URL(self) -> str:
    """Автоматически собирает строку подключения для asyncpg."""
    return (
        f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
        f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    )
```

Формирует DSN для драйвера `asyncpg` на основе полей класса.

> ⚠️ **Замечание**: `model_config = SettingsConfigDict(env_file=".env", ...)` в классе присутствует, но фактически `.env` не используется — значения берутся из дефолтов. При добавлении `.env`-файла настройки автоматически начнут из него подгружаться.

### Использование

```python
from core.config import Settings

settings = Settings()
print(settings.DATABASE_URL)
# postgresql+asyncpg://postgres:admin@localhost:5432/vuxhubbd
```

---

## 🗄 core/database — Асинхронная сессия БД

### Назначение
Создаёт `async_engine`, `async_sessionmaker`, базовый класс моделей и dependency для FastAPI.

### Основные объекты

| Объект | Тип | Назначение |
|---|---|---|
| `engine` | `AsyncEngine` | Асинхронный движок SQLAlchemy |
| `AsyncSessionLocal` | `async_sessionmaker[AsyncSession]` | Фабрика сессий |
| `Base` | `DeclarativeBase` | Базовый класс ORM-моделей |
| `get_db` | `AsyncGenerator[AsyncSession]` | FastAPI dependency |

### Правила
- **Одна сессия на HTTP-запрос** — через `Depends(get_db)`.
- `commit()` — в CRUD/service слое.
- `rollback()` — автоматически при исключении.
- Включён `pool_pre_ping=True` для защиты от «мертвых» соединений.

---

## 🧱 models — ORM-модели

- Наследуются от `Base` (`core.database`).
- `__tablename__` — snake_case, множественное число.
- Обязательные поля: `id` (PK), `created_at`, `updated_at`.

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

---

## 📦 schemas — DTO (Pydantic)

- Разделение по назначению: `Create` / `Update` / `Read` / `Filter`.
- `Read`-схемы используют `ConfigDict(from_attributes=True)`.

```python
class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

## 🔁 crud — CRUD-классы (строго Singleton)

### Требования
- **Один экземпляр на всё приложение** (Singleton через метакласс).
- Только атомарные операции с БД, без бизнес-логики.
- Методы: `get`, `get_multi`, `create`, `update`, `delete`.

### Схема Singleton

```python
class SingletonMeta(type):
    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
```

### Пример

```python
class UserCRUD(BaseCRUD[User]):
    model = User

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


user_crud = UserCRUD()  # singleton
```

---

## 🧠 services — Бизнес-логика (Singleton, аналогично CRUD)

- Тот же `SingletonMeta`.
- Инкапсулируют правила домена: хеширование, проверки, оркестрация CRUD.
- Бросают `HTTPException` / доменные исключения.

```python
class UserService(metaclass=SingletonMeta):

    async def create_user(self, db: AsyncSession, data: UserCreate):
        if await user_crud.get_by_email(db, data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email уже занят")
        hashed = self._hash_password(data.password)
        return await user_crud.create(
            db, email=data.email, username=data.username, hashed_password=hashed
        )


user_service = UserService()
```

---

## 🌐 api — Эндпоинты FastAPI

### Правила
- Роутеры в `api/`, регистрируются через `include_router` в `main.py`.
- `prefix` и `tags` задаются в `APIRouter`.
- БД — через `Depends(get_db)`.
- Авторизация — через `Depends(verify_token)` (использует `AUTH_CHECK_URL`).

### Зависимость проверки токена

```python
async def verify_token(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid scheme")
    token = authorization.removeprefix("Bearer ").strip()

    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            settings.AUTH_CHECK_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")
    return resp.json()
```

### Роутер пользователей

```python
router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    return await user_service.create_user(db, payload)

@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user(db, user_id)

@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_token),
):
    return await user_service.update_user(db, user_id, payload)

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_token),
):
    await user_service.delete_user(db, user_id)
```

---

## 📋 Сводная таблица эндпоинтов

| Метод | Путь | Auth | Тело запроса | Ответ | Описание |
|---|---|---|---|---|---|
| `POST` | `/users` | ❌ | `UserCreate` | `UserRead` | Создать пользователя |
| `GET` | `/users/{user_id}` | ❌ | — | `UserRead` | Получить пользователя по ID |
| `PATCH` | `/users/{user_id}` | ✅ | `UserUpdate` | `UserRead` | Обновить пользователя |
| `DELETE` | `/users/{user_id}` | ✅ | — | `204 No Content` | Удалить пользователя |

---

## 🧭 Правила слоёв

```
api  →  services  →  crud  →  models
         (логика)   (Singleton)  (ORM)
              ↑
           schemas (DTO)
```

1. **api** — валидация входа/выхода, вызов сервиса. Никаких SQL-запросов.
2. **services** — бизнес-правила, транзакции, вызов нескольких CRUD.
3. **crud** — атомарные операции с БД, **строго Singleton**.
4. **models** — только описание таблиц.
5. **schemas** — только контракты API.

### Запрещено
- Импортировать `models` напрямую в `api`.
- Импортировать `crud` напрямую в `api` (только через `services`).
- Хранить `AsyncSession` в Singleton-классах — сессия передаётся параметром в методы.

---

## 🚀 Запуск

```bash
uvicorn main:app --reload
```

- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

---

## 📝 Заметки о текущем состоянии

- **Конфиг** хранится в `core/config.py`. Класс `Settings` уже подготовлен к чтению `.env` (через `SettingsConfigDict`), так что при появлении `.env` настройки подхватятся без изменений кода.
- **`SECRET_JWT_KEY = "qwert"`** — дефолтное значение, перед продакшеном заменить.
- **`AUTH_CHECK_URL`** указывает на `https://localhost:3100` — сервис проверки авторизации, `verify=False` в httpx используется из-за самоподписанного сертификата (актуально только для локальной разработки).