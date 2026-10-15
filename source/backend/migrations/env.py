import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from models.models import Base

# 1. Это стандартная настройка логирования Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. ИМПОРТИРУЙТЕ СЮДА ВАШ METADATA ИЗ ПРОЕКТА
# Вместо этой строки укажите ваш реальный путь к Base:
# Пример: from app.db import Base
target_metadata = Base.metadata
# target_metadata = None


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Вспомогательная функция для выполнения миграций в синхронном контексте."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме (асинхронный вариант)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync выполняет синхронную функцию do_run_migrations в асинхронном окружении
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Запускаем асиненхронную функцию через asyncio
    asyncio.run(run_migrations_online())
