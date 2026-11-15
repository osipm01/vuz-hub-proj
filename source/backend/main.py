import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Явный импорт моделей регистрирует все таблицы в едином
# реестре метаданных SQLAlchemy (Base.metadata). Без этого
# внешние ключи между таблицами из разных файлов моделей
# не находятся и приводят к NoReferencedTableError.
import models  # noqa: F401

from routers import (
    debts,
    dops,
    groups,
    schedules,
    subjects,
    users,
    user_subjects,
    auth_router,
    integrations_router
)
from core.config import settings
from drivers.redis import RedisDriver

# Читаем имя сервиса из переменной окружения (по умолчанию запускаем всё как монолит)
SERVICE_NAME = os.getenv("SERVICE_NAME", "monolith").lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Инициализация Redis ----
    redis_driver = RedisDriver(
        url=settings.REDIS_URL,
        key_prefix=settings.REDIS_KEY_PREFIX,
    )
    try:
        await redis_driver.connect()
        app.state.redis = redis_driver
    except Exception:
        # Redis опционален — приложение стартует без него
        app.state.redis = None

    yield

    # ---- Закрытие Redis ----
    redis: RedisDriver | None = getattr(app.state, "redis", None)
    if redis is not None:
        await redis.close()


def create_app() -> FastAPI:
    # 1. Инициализируем базовое приложение
    app = FastAPI(
        title=f"My API [{SERVICE_NAME.upper()}]",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — временно разрешаем всё, потом настроим по умолчанию
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["Health"], summary="Проверка работы API")
    async def root():
        return {"status": "OK", "service": SERVICE_NAME}

    # 2. Подключаем роутеры в зависимости от выбранного режима
    if SERVICE_NAME == "monolith":
        # Запуск всего приложения целиком (как у вас было)
        app.include_router(auth_router.router, tags=["Auth"])
        app.include_router(users.router, tags=["Users"])
        app.include_router(groups.router, tags=["Groups"])
        app.include_router(schedules.router, tags=["Schedules"])
        app.include_router(subjects.router, tags=["Subjects"])
        app.include_router(user_subjects.router, tags=["User-Subjects"])
        app.include_router(debts.router, tags=["Debts"])
        app.include_router(dops.router, tags=["Dops"])
        app.include_router(integrations_router.router, tags=["Integration"])

    elif SERVICE_NAME == "auth-service":
        # Сервис авторизации и пользователей
        app.include_router(auth_router.router, tags=["Auth"])
        app.include_router(users.router, tags=["Users"])

    elif SERVICE_NAME == "study-service":
        # Сервис расписания, групп и предметов
        app.include_router(groups.router, tags=["Groups"])
        app.include_router(schedules.router, tags=["Schedules"])
        app.include_router(subjects.router, tags=["Subjects"])
        app.include_router(user_subjects.router, tags=["User-Subjects"])

    elif SERVICE_NAME == "finance-service":
        # Сервис долгов и доп. услуг
        app.include_router(debts.router, tags=["Debts"])
        app.include_router(dops.router, tags=["Dops"])

    elif SERVICE_NAME == "integration-service":
        # Сервис интеграций
        app.include_router(integrations_router.router, tags=["Integration"])

    else:
        raise ValueError(f"Неизвестный SERVICE_NAME: {SERVICE_NAME}")

    return app

app = create_app()
