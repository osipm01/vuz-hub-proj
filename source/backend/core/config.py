from __future__ import annotations

import os
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # SERVICE
    # ------------------------------------------------------------------ #
    SERVICE_NAME: str = "monolith"

    # ------------------------------------------------------------------ #
    # AUTH / JWT
    # ------------------------------------------------------------------ #
    SECRET_JWT_KEY: str = "qwert"
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ------------------------------------------------------------------ #
    # DATABASE  (базовые поля, используемые микросервисами)
    # ------------------------------------------------------------------ #
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "admin"
    DB_NAME: str = "vuzhubbd"

    # ------------------------------------------------------------------ #
    # REDIS
    # ------------------------------------------------------------------ #
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ------------------------------------------------------------------ #
    # computed properties
    # ------------------------------------------------------------------ #

    @property
    def DATABASE_URL(self) -> str:
        """
        Строка подключения для async engine (asyncpg).

        В режиме монолита берёт DATABASE_URL из окружения напрямую
        (файл .env содержит DATABASE_URL=...).
        В режиме микросервиса — конструирует из отдельных полей.
        """
        if self.SERVICE_NAME != "monolith":
            return (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        # Монолит: может быть задано в .env напрямую
        url = os.environ.get("DATABASE_URL")
        if url:
            return url
        # Fallback — конструируем из полей
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def ALEMBIC_DATABASE_URL(self) -> str:
        """Строка подключения для alembic (синхронный driver)."""
        if self.SERVICE_NAME != "monolith":
            return (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        url = os.environ.get("DATABASE_URL")
        if url:
            # Для alembic заменяем driver на psycopg2 (sync)
            return url.replace("postgresql+asyncpg://", "postgresql://")
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
