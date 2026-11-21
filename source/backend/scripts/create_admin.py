# scripts/create_admin.py
"""
Создание администратора.

Запуск (из корня проекта):
    python -m scripts.create_admin                          # использует .env.auth по умолчанию
    python -m scripts.create_admin --db-url <url>           # прямой URL БД
    python -m scripts.create_admin --email admin@example.com --name "Admin" --telegram-id 123456789
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для прямого запуска
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _is_in_docker() -> bool:
    """Проверяем, запущен ли скрипт внутри Docker-контейнера."""
    return Path("/.dockerenv").exists() or "DOCKER_CONTAINER" in os.environ


def _adapt_env_for_local() -> None:
    """
    При локальном запуске (не в Docker) подменяет Docker-хосты на localhost.

    Docker-compose мапит порты БД так:
      auth-db     → 5432
      study-db    → 5433
      finance-db  → 5434
      integration-db → 5435
      redis       → 6379
    """
    docker_hosts = {
        "auth-db": ("localhost", "5432"),
        "study-db": ("localhost", "5433"),
        "finance-db": ("localhost", "5434"),
        "integration-db": ("localhost", "5435"),
        "redis": ("localhost", "6379"),
    }

    current_host = os.environ.get("DB_HOST", "")
    current_redis_host = os.environ.get("REDIS_HOST", "")

    if current_host in docker_hosts:
        localhost, port = docker_hosts[current_host]
        os.environ["DB_HOST"] = localhost
        os.environ["DB_PORT"] = port
        print(f"  🔄 DB_HOST: {current_host} → {localhost}:{port}")

    if current_redis_host in docker_hosts:
        localhost, port = docker_hosts[current_redis_host]
        os.environ["REDIS_HOST"] = localhost
        os.environ["REDIS_PORT"] = port
        print(f"  🔄 REDIS_HOST: {current_redis_host} → {localhost}:{port}")


def _load_env_file(path: str) -> None:
    """Загружает переменные окружения из .env-файла (без сторонних библиотек)."""
    env_path = Path(path)
    if not env_path.exists():
        print(f"⚠️  Файл {path} не найден, переменные окружения не загружаются.")
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


async def create_admin(
    name: str,
    email: str,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    max_id: int | None = None,
    group_id: int | None = None,
    promote_existing: bool = True,
) -> None:
    # Импортируем внутри async-функции, после загрузки .env
    from sqlalchemy import select

    from core.database import AsyncSessionLocal
    from models.auth import User
    from enums.user_enums import UserRole

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  Пользователь с email {email} уже существует (id={existing.id}, role={existing.role}).")
            if promote_existing and existing.role != UserRole.ADMIN:
                existing.role = UserRole.ADMIN
                await session.commit()
                await session.refresh(existing)
                print(f"✅ Пользователь {email} повышен до ADMIN.")
            return

        # Проверка уникальности telegram_id, если задан
        if telegram_id is not None:
            tg_exists = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            if tg_exists.scalar_one_or_none():
                raise ValueError(f"Пользователь с telegram_id={telegram_id} уже существует")

        admin = User(
            name=name,
            email=email,
            role=UserRole.ADMIN,
            group_id=group_id,
            telegram_id=telegram_id,
            VK_id=vk_id,
            MAX_id=max_id,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

        print(
            f"✅ Администратор создан: "
            f"id={admin.id}, email={admin.email}, role={admin.role}, "
            f"telegram_id={admin.telegram_id}"
        )


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Создание администратора",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Подключиться к БД auth (по умолчанию из .env.auth):
  python -m scripts.create_admin

  # Указать URL БД напрямую:
  python -m scripts.create_admin --db-url "postgresql+asyncpg://postgres:admin@localhost:5432/vuzhub_auth"

  # Указать .env-файл другого сервиса:
  python -m scripts.create_admin --env-file .env.auth

  # Свой email и имя:
  python -m scripts.create_admin --email admin@myuniversity.ru --name "Иванов И.И."
        """,
    )
    parser.add_argument("--name", default="Administrator", help="Имя администратора")
    parser.add_argument("--email", default="admin@example.com", help="Email администратора")
    parser.add_argument("--telegram-id", type=int, default=None, help="Telegram ID")
    parser.add_argument("--vk-id", type=int, default=None, help="VK ID")
    parser.add_argument("--max-id", type=int, default=None, help="MAX ID")
    parser.add_argument("--group-id", type=int, default=None, help="ID группы (опционально)")
    parser.add_argument(
        "--db-url",
        default=None,
        help="Прямой URL подключения к БД (переопределяет .env)",
    )
    parser.add_argument(
        "--env-file",
        default=".env.auth",
        help="Путь к .env-файлу (по умолчанию .env.auth)",
    )
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Не повышать существующего пользователя до ADMIN",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent

    # 1. Загружаем переменные из .env-файла
    env_file = project_root / args.env_file
    print(f"📄 Загрузка {env_file}...")
    _load_env_file(str(env_file))

    # 2. Если запускаемся локально (не в Docker), подменяем хосты на localhost
    if not _is_in_docker():
        print("🔄 Запуск локально — подменяю Docker-хосты на localhost\n")
        _adapt_env_for_local()
        print()

    # 3. Если указан --db-url, ставим его поверх всего
    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url
        print(f"🔗 Используем URL БД: {args.db_url}")

    # 4. Переопределяем SERVICE_NAME, чтобы database.py использовал монолитный режим
    os.environ["SERVICE_NAME"] = "monolith"

    db_url = os.environ.get("DATABASE_URL", "N/A")
    print(f"✅ Готово. Подключение к БД: {db_url}")
    print()

    asyncio.run(
        create_admin(
            name=args.name,
            email=args.email,
            telegram_id=args.telegram_id,
            vk_id=args.vk_id,
            max_id=args.max_id,
            group_id=args.group_id,
            promote_existing=not args.no_promote,
        )
    )


if __name__ == "__main__":
    main()