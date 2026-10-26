# scripts/create_admin.py
"""
Создание администратора.

Запуск:
    python -m scripts.create_admin
    python -m scripts.create_admin --email admin@example.com --name "Admin" --telegram-id 123456789
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для прямого запуска
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.models import User
from enums.user_enums import UserRole


async def create_admin(
    name: str,
    email: str,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    max_id: int | None = None,
    group_id: int | None = None,
    promote_existing: bool = True,
) -> User:
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
            return existing

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
        return admin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создание администратора")
    parser.add_argument("--name", default="Administrator", help="Имя администратора")
    parser.add_argument("--email", default="admin@example.com", help="Email администратора")
    parser.add_argument("--telegram-id", type=int, default=None, help="Telegram ID")
    parser.add_argument("--vk-id", type=int, default=None, help="VK ID")
    parser.add_argument("--max-id", type=int, default=None, help="MAX ID")
    parser.add_argument("--group-id", type=int, default=None, help="ID группы (опционально)")
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Не повышать существующего пользователя до ADMIN",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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