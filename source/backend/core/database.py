"""
Асинхронный engine + sessionmaker для SQLAlchemy.

Поддерживает как монолитный запуск (одна БД), так и
микросервисный (каждый сервис подключается к своей БД
через settings.DB_HOST / settings.DB_NAME).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  ENGINE / SESSION  (инициализируются один раз при старте)
# ------------------------------------------------------------------ #

if settings.SERVICE_NAME != "monolith":
    database_url = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
else:
    database_url = settings.DATABASE_URL

# 2. Инициализируем engine с правильным URL
engine = create_async_engine(
    database_url, # <-- Передаем вычисленный URL
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
# Базовый класс для моделей
Base: DeclarativeBase = DeclarativeBase()


# ------------------------------------------------------------------ #
#  DEPENDENCY  (для FastAPI)
# ------------------------------------------------------------------ #

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: открывает сессию на запрос и закрывает после."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ------------------------------------------------------------------ #
#  ENGINE / SESSION  factories  (для микросервисов)
# ------------------------------------------------------------------ #

def create_service_engine(db_name: str | None = None, db_host: str | None = None):
    """
    Создать отдельный engine для микросервиса.

    Если SERVICE_NAME != "monolith" — engine создаётся
    из settings.DB_HOST / settings.DB_NAME (переопределённых
    через .env-файл конкретного сервиса).
    """
    url = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{db_host or settings.DB_HOST}:{settings.DB_PORT}/{db_name or settings.DB_NAME}"
    return create_async_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
    )
