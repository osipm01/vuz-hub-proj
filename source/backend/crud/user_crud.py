from __future__ import annotations

import logging
from typing import Final, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from enums.user_enums import SocialNetworkLinkType, UserRole
from models.models import User
from schemas.user_schema import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

_SOCIAL_FIELD_MAP: Final[dict[SocialNetworkLinkType, str]] = {
    SocialNetworkLinkType.VK: "VK_id",
    SocialNetworkLinkType.MAX_id: "MAX_id",
    SocialNetworkLinkType.TG_ID: "telegram_id",
}


class UserCRUD:
    """Репозиторий пользователей. Используется как модульный синглтон."""

    def __init__(self) -> None:
        self.social_field_map: Final[dict[SocialNetworkLinkType, str]] = _SOCIAL_FIELD_MAP

    # ---------- helpers ----------

    def get_social_field(self, link_type: SocialNetworkLinkType) -> str:
        try:
            return self.social_field_map[link_type]
        except KeyError as exc:
            logger.error("get_social_field: неизвестный link_type=%s", link_type)
            raise ValueError(f"Неизвестный тип соцсети: {link_type!r}") from exc

    # ---------- CREATE ----------

    async def create_user(
        self,
        db: AsyncSession,
        data: UserCreate,
        role: UserRole = UserRole.USER,
    ) -> User:
        logger.debug("create_user: email=%r role=%s", data.email, role.value)
        user = User(**data.model_dump(), role=role)
        db.add(user)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            logger.error(
                "create_user: IntegrityError email=%r err=%s", data.email, exc
            )
            raise
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("create_user: SQLAlchemyError email=%r", data.email)
            raise
        except Exception:
            await db.rollback()
            logger.exception("create_user: unexpected error email=%r", data.email)
            raise

        logger.info("create_user: создан user.id=%s email=%r", user.id, user.email)
        return user

    # ---------- READ ----------

    async def get_user(self, db: AsyncSession, user_id: int) -> Optional[User]:
        logger.debug("get_user: id=%s", user_id)
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_user: SQLAlchemyError id=%s", user_id)
            raise
        except Exception:
            logger.exception("get_user: unexpected error id=%s", user_id)
            raise

        if user is None:
            logger.warning("get_user: не найден id=%s", user_id)
        return user

    async def get_user_by_email(
        self, db: AsyncSession, email: str
    ) -> Optional[User]:
        logger.debug("get_user_by_email: email=%r", email)
        try:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_user_by_email: SQLAlchemyError email=%r", email)
            raise
        except Exception:
            logger.exception("get_user_by_email: unexpected error email=%r", email)
            raise

        if user is None:
            logger.warning("get_user_by_email: не найден email=%r", email)
        return user

    async def get_user_by_social(
        self,
        db: AsyncSession,
        link_type: SocialNetworkLinkType,
        social_id: int,
    ) -> Optional[User]:
        logger.debug(
            "get_user_by_social: link_type=%s social_id=%r", link_type, social_id
        )
        field = self.get_social_field(link_type)
        stmt = select(User).where(getattr(User, field) == social_id)

        try:
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(
                "get_user_by_social: SQLAlchemyError link_type=%s social_id=%r",
                link_type, social_id,
            )
            raise
        except Exception:
            logger.exception(
                "get_user_by_social: unexpected error link_type=%s social_id=%r",
                link_type, social_id,
            )
            raise

        if user is None:
            logger.warning(
                "get_user_by_social: не найден link_type=%s social_id=%r",
                link_type, social_id,
            )
        return user

    async def get_user_with_relations(
        self, db: AsyncSession, user_id: int
    ) -> Optional[User]:
        logger.debug("get_user_with_relations: id=%s", user_id)
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                joinedload(User.group),
                selectinload(User.debts),
                selectinload(User.user_subjects),
                selectinload(User.dops),
            )
        )
        try:
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(
                "get_user_with_relations: SQLAlchemyError id=%s", user_id
            )
            raise
        except Exception:
            logger.exception(
                "get_user_with_relations: unexpected error id=%s", user_id
            )
            raise

        if user is None:
            logger.warning("get_user_with_relations: не найден id=%s", user_id)
        return user

    async def get_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
    ) -> Sequence[User]:
        logger.debug(
            "get_users: skip=%s limit=%s group_id=%s", skip, limit, group_id
        )
        if skip < 0 or limit <= 0:
            logger.error(
                "get_users: некорректная пагинация skip=%s limit=%s", skip, limit
            )
            raise ValueError(
                f"Некорректные параметры пагинации: skip={skip}, limit={limit}"
            )

        stmt = select(User).order_by(User.id)
        if group_id is not None:
            stmt = stmt.where(User.group_id == group_id)
        stmt = stmt.offset(skip).limit(limit)

        try:
            result = await db.execute(stmt)
            users = result.scalars().all()
        except SQLAlchemyError:
            logger.exception(
                "get_users: SQLAlchemyError skip=%s limit=%s group_id=%s",
                skip, limit, group_id,
            )
            raise
        except Exception:
            logger.exception(
                "get_users: unexpected error skip=%s limit=%s group_id=%s",
                skip, limit, group_id,
            )
            raise

        logger.debug("get_users: получено %d записей", len(users))
        return users

    # ---------- UPDATE ----------

    async def update_user(
        self, db: AsyncSession, user: User, data: UserUpdate
    ) -> User:
        logger.debug("update_user: user.id=%s fields=%r", user.id, data.model_fields_set)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            logger.error(
                "update_user: IntegrityError user.id=%s fields=%r",
                user.id, list(update_data),
            )
            raise ValueError(
                "Не удалось обновить пользователя (дубликат данных)"
            ) from exc
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("update_user: SQLAlchemyError user.id=%s", user.id)
            raise
        except Exception:
            await db.rollback()
            logger.exception("update_user: unexpected error user.id=%s", user.id)
            raise

        logger.info(
            "update_user: обновлён user.id=%s fields=%s",
            user.id, list(update_data),
        )
        return user

    async def update_role(
        self, db: AsyncSession, user: User, role: UserRole
    ) -> User:
        logger.debug("update_role: user.id=%s new_role=%s", user.id, role.value)
        old_role = user.role
        user.role = role

        try:
            await db.commit()
            await db.refresh(user)
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("update_role: SQLAlchemyError user.id=%s", user.id)
            raise
        except Exception:
            await db.rollback()
            logger.exception("update_role: unexpected error user.id=%s", user.id)
            raise

        logger.info(
            "update_role: user.id=%s %s -> %s", user.id, old_role, role.value
        )
        return user

    # ---------- SOCIAL LINKS ----------

    async def link_social(
        self,
        db: AsyncSession,
        user: User,
        link_type: SocialNetworkLinkType,
        social_id: int,
    ) -> User:
        logger.debug(
            "link_social: user.id=%s link_type=%s social_id=%r",
            user.id, link_type, social_id,
        )
        field = self.get_social_field(link_type)

        existing = await self.get_user_by_social(db, link_type, social_id)
        if existing is not None and existing.id != user.id:
            logger.warning(
                "link_social: занято link_type=%s social_id=%r existing.id=%s user.id=%s",
                link_type, social_id, existing.id, user.id,
            )
            raise ValueError(
                f"{link_type.value}={social_id} уже привязан к user.id={existing.id}"
            )

        setattr(user, field, social_id)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            logger.error(
                "link_social: IntegrityError user.id=%s link_type=%s social_id=%r",
                user.id, link_type, social_id,
            )
            raise ValueError(
                f"Этот {link_type.value} ID уже был привязан другим пользователем"
            ) from exc
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("link_social: SQLAlchemyError user.id=%s", user.id)
            raise
        except Exception:
            await db.rollback()
            logger.exception("link_social: unexpected error user.id=%s", user.id)
            raise

        logger.info(
            "link_social: user.id=%s link_type=%s social_id=%r",
            user.id, link_type, social_id,
        )
        return user

    async def unlink_social(
        self,
        db: AsyncSession,
        user: User,
        link_type: SocialNetworkLinkType,
    ) -> User:
        logger.debug("unlink_social: user.id=%s link_type=%s", user.id, link_type)
        field = self.get_social_field(link_type)
        setattr(user, field, None)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as exc:
            await db.rollback()
            logger.error(
                "unlink_social: IntegrityError user.id=%s link_type=%s",
                user.id, link_type,
            )
            raise ValueError(
                "Невозможно отвязать соцсеть (поле не может быть NULL)"
            ) from exc
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("unlink_social: SQLAlchemyError user.id=%s", user.id)
            raise
        except Exception:
            await db.rollback()
            logger.exception("unlink_social: unexpected error user.id=%s", user.id)
            raise

        logger.info("unlink_social: user.id=%s link_type=%s", user.id, link_type)
        return user

    async def get_user_by_telegram_id(
        self, db: AsyncSession, telegram_id: int
    ) -> Optional[User]:
        return await self.get_user_by_social(
            db, SocialNetworkLinkType.TG_ID, telegram_id
        )

    async def get_user_by_vk_id(
        self, db: AsyncSession, vk_id: int
    ) -> Optional[User]:
        return await self.get_user_by_social(db, SocialNetworkLinkType.VK, vk_id)

    async def get_user_by_max_id(
        self, db: AsyncSession, max_id: int
    ) -> Optional[User]:
        return await self.get_user_by_social(db, SocialNetworkLinkType.MAX_id, max_id)

    # ---------- DELETE ----------

    async def delete_user(self, db: AsyncSession, user: User) -> bool:
        logger.debug("delete_user: user.id=%s", user.id)
        await db.delete(user)

        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            logger.error("delete_user: IntegrityError user.id=%s", user.id)
            raise ValueError(
                "Невозможно удалить пользователя: существуют связанные записи"
            ) from exc
        except SQLAlchemyError:
            await db.rollback()
            logger.exception("delete_user: SQLAlchemyError user.id=%s", user.id)
            raise
        except Exception:
            await db.rollback()
            logger.exception("delete_user: unexpected error user.id=%s", user.id)
            raise

        logger.info("delete_user: удалён user.id=%s", user.id)
        return True


user_crud: Final[UserCRUD] = UserCRUD()