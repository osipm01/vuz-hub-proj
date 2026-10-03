from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schemas.user_schema import UserCreate, UserUpdate
from models.models import User


# ---------- CREATE ----------

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(**data.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------- READ (одиночные) ----------

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
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
) -> User:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------- DELETE ----------

async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.commit()