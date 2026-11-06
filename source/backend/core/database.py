"""
Асинхронный engine + sessionmaker для SQLAlchemy.

В режиме монолита использует settings.DATABASE_URL напрямую
(читается из .env или DATABASE_URL из окружения).

В режиме микросервиса динамически конструирует URL из параметров:
    settings.DB_USER / DB_PASSWORD / DB_HOST / DB_PORT / DB_NAME
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  ДИНАМИЧЕСКАЯ КОНСТРУКЦИЯ DATABASE_URL
# ------------------------------------------------------------------ #

if settings.SERVICE_NAME != "monolith":
    # Микросервисный режим: URL конструируется из переменных окружения.
    # Docker Compose передаёт DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT
    # через environment:, поэтому они доступны через os.environ / settings.
    _db_user = os.environ.get("DB_USER", settings.DB_USER)
    _db_pass = os.environ.get("DB_PASSWORD", settings.DB_PASSWORD)
    _db_host = os.environ.get("DB_HOST", settings.DB_HOST)
    _db_port = os.environ.get("DB_PORT", str(settings.DB_PORT))
    _db_name = os.environ.get("DB_NAME", settings.DB_NAME)

    database_url = (
        f"postgresql+asyncpg://{_db_user}:{_db_pass}"
        f"@{_db_host}:{_db_port}/{_db_name}"
    )
    logger.info(
        "[DATABASE] SERVICE_NAME=%s DB=%s@%s:%s",
        settings.SERVICE_NAME, _db_name, _db_host, _db_port,
    )
else:
    # Монолитный режим: берём DATABASE_URL из окружения (файл .env или переменная).
    database_url = settings.DATABASE_URL
    logger.info(
        "[DATABASE] SERVICE_NAME=monolith DB=%s:%s/%s",
        settings.DB_HOST, settings.DB_PORT, settings.DB_NAME,
    )

# ------------------------------------------------------------------ #
#  ENGINE / SESSION
# ------------------------------------------------------------------ #

engine = create_async_engine(
    database_url,
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
