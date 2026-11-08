import os
from fastapi import FastAPI

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

# Читаем имя сервиса из переменной окружения (по умолчанию запускаем всё как монолит)
SERVICE_NAME = os.getenv("SERVICE_NAME", "monolith").lower()

def create_app() -> FastAPI:
    # 1. Инициализируем базовое приложение
    app = FastAPI(title=f"My API [{SERVICE_NAME.upper()}]", version="0.1.0")

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
