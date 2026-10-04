from typing import Optional, Sequence, Dict
from enum import Enum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError  # важно: не sqlite3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schemas.user_schema import UserCreate, UserUpdate
from models.models import User


class SocialNetworkLinkType(Enum):
    VK = "vk"
    MAX_id = "max_id"
    TG_ID = "tg_id"


# Соответствие: тип соцсети -> имя поля в модели User
_SOCIAL_FIELD_MAP: Dict[SocialNetworkLinkType, str] = {
    SocialNetworkLinkType.VK: "VK_id",
    SocialNetworkLinkType.MAX_id: "MAX_id",
    SocialNetworkLinkType.TG_ID: "telegram_id",
}


# ---------- CREATE ----------

async def create_user(db: AsyncSession, data: UserCreate) -> Optional[User]:
    user = User(**data.model_dump())
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        print(f"DB IntegrityError in create_user: {e}")
        return None
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error in create_user: {e}")
        raise

    return user



async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_social(
    db: AsyncSession,
    link_type: SocialNetworkLinkType,
    social_id: int | str,
) -> Optional[User]:
    """Находит пользователя по id в конкретной соцсети."""
    field = _SOCIAL_FIELD_MAP[link_type]
    stmt = select(User).where(getattr(User, field) == social_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_with_relations(
    db: AsyncSession, user_id: int
) -> Optional[User]:
    """Загружает пользователя вместе со всеми связями (избегает N+1)."""
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.group),
            selectinload(User.debts),
            selectinload(User.user_subjects),
            selectinload(User.dops),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------- READ (списки) ----------

async def get_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    group_id: Optional[int] = None,
) -> Sequence[User]:
    stmt = select(User).offset(skip).limit(limit).order_by(User.id)
    if group_id is not None:
        stmt = stmt.where(User.group_id == group_id)
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------- UPDATE ----------

async def update_user(
    db: AsyncSession, user: User, data: UserUpdate
) -> Optional[User]:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        print(f"DB IntegrityError in update_user: {e}")
        return None          # либо: raise ValueError(...) from e
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error in update_user: {e}")
        raise

    return user


# ---------- SOCIAL LINKS ----------

async def link_social(
    db: AsyncSession,
    user: User,
    link_type: SocialNetworkLinkType,
    social_id: int | str,
) -> Optional[User]:
    """Привязывает аккаунт соцсети к пользователю.

    Если такой social_id уже привязан к другому пользователю — бросает ValueError.
    """
    field = _SOCIAL_FIELD_MAP[link_type]

    # проверяем, не занят ли этот social_id другим пользователем
    existing = await get_user_by_social(db, link_type, social_id)
    if existing is not None and existing.id != user.id:
        raise ValueError(
            f"{link_type.value}={social_id} уже привязан к user.id={existing.id}"
        )

    setattr(user, field, social_id)
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        print(f"DB IntegrityError in link_social: {e}")
        return None          # либо: raise ValueError(...) from e
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error in link_social: {e}")
        raise

    return user


async def unlink_social(
    db: AsyncSession,
    user: User,
    link_type: SocialNetworkLinkType,
) -> Optional[User]:
    """Отвязывает аккаунт соцсети от пользователя."""
    field = _SOCIAL_FIELD_MAP[link_type]
    setattr(user, field, None)
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        print(f"DB IntegrityError in unlink_social: {e}")
        return None
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error in unlink_social: {e}")
        raise

    return user


async def get_user_by_telegram_id(
    db: AsyncSession, telegram_id: int | str
) -> Optional[User]:
    return await get_user_by_social(db, SocialNetworkLinkType.TG_ID, telegram_id)


async def get_user_by_vk_id(
    db: AsyncSession, vk_id: int | str
) -> Optional[User]:
    return await get_user_by_social(db, SocialNetworkLinkType.VK, vk_id)


async def get_user_by_max_id(
    db: AsyncSession, max_id: int | str
) -> Optional[User]:
    return await get_user_by_social(db, SocialNetworkLinkType.MAX_id, max_id)


# ---------- DELETE ----------

async def delete_user(db: AsyncSession, user: User) -> bool:
    await db.delete(user)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        print(f"DB IntegrityError in delete_user: {e}")
        return False
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error in delete_user: {e}")
        raise

    return True