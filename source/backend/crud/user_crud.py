import logging
from typing import Optional, Sequence, Dict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from schemas.user_schema import UserCreate, UserUpdate
from models.models import User
from enums.user_enums import SocialNetworkLinkType

logger = logging.getLogger(__name__)


# Соответствие: тип соцсети -> имя поля в модели User
_SOCIAL_FIELD_MAP: Dict[SocialNetworkLinkType, str] = {
    SocialNetworkLinkType.VK: "VK_id",
    SocialNetworkLinkType.MAX_id: "MAX_id",
    SocialNetworkLinkType.TG_ID: "telegram_id",
}


class UserCRUD:
    """Синглтон-репозиторий для работы с пользователями."""

    _instance: Optional["UserRepository"] = None
    _initialized: bool = False

    def __new__(cls) -> "UserRepository":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._social_field_map: Dict[SocialNetworkLinkType, str] = _SOCIAL_FIELD_MAP
        self.__class__._initialized = True

    # ---------- CREATE ----------

    async def create_user(self, db: AsyncSession, data: UserCreate) -> User:
        logger.debug("create_user: data=%r", data)
        user = User(**data.model_dump())
        db.add(user)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in create_user: email=%r, data=%r, err=%s",
                getattr(data, "email", None), data, e,
            )
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_user: data=%r, err=%s", data, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_user: data=%r, err=%s", data, e)
            raise

        logger.info("create_user: создан user.id=%s, email=%r", user.id, user.email)
        return user

    # ---------- READ ----------

    async def get_user(self, db: AsyncSession, user_id: int) -> Optional[User]:
        logger.debug("get_user: id=%s", user_id)
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_user: id=%s, err=%s", user_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_user: id=%s, err=%s", user_id, e)
            raise

        if user is None:
            logger.warning("get_user: пользователь не найден, id=%s", user_id)
        else:
            logger.debug("get_user: найден user.id=%s", user.id)
        return user

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        logger.debug("get_user_by_email: email=%r", email)
        try:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_user_by_email: email=%r, err=%s", email, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_user_by_email: email=%r, err=%s", email, e)
            raise

        if user is None:
            logger.warning("get_user_by_email: не найден, email=%r", email)
        return user

    async def get_user_by_social(
        self,
        db: AsyncSession,
        link_type: SocialNetworkLinkType,
        social_id: int | str,
    ) -> Optional[User]:
        logger.debug("get_user_by_social: link_type=%s, social_id=%r", link_type, social_id)
        try:
            field = self._social_field_map[link_type]
        except KeyError as e:
            logger.error("get_user_by_social: неизвестный link_type=%s", link_type)
            raise ValueError(f"Неизвестный тип соцсети: {link_type!r}") from e

        stmt = select(User).where(getattr(User, field) == social_id)
        try:
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_user_by_social: link_type=%s, social_id=%r, err=%s",
                link_type, social_id, e,
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_user_by_social: link_type=%s, social_id=%r, err=%s",
                link_type, social_id, e,
            )
            raise

        if user is None:
            logger.warning(
                "get_user_by_social: не найден, link_type=%s, social_id=%r",
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
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_user_with_relations: id=%s, err=%s", user_id, e
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_user_with_relations: id=%s, err=%s", user_id, e
            )
            raise

        if user is None:
            logger.warning("get_user_with_relations: не найден, id=%s", user_id)
        return user

    async def get_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
    ) -> Sequence[User]:
        logger.debug(
            "get_users: skip=%s, limit=%s, group_id=%s", skip, limit, group_id
        )
        if skip < 0 or limit <= 0:
            logger.error(
                "get_users: некорректные параметры пагинации, skip=%s, limit=%s",
                skip, limit,
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
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_users: skip=%s, limit=%s, group_id=%s, err=%s",
                skip, limit, group_id, e,
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_users: skip=%s, limit=%s, group_id=%s, err=%s",
                skip, limit, group_id, e,
            )
            raise

        logger.debug("get_users: получено %d записей", len(users))
        return users

    # ---------- UPDATE ----------

    async def update_user(
        self, db: AsyncSession, user: User, data: UserUpdate
    ) -> Optional[User]:
        logger.debug("update_user: user.id=%s, data=%r", user.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in update_user: user.id=%s, data=%r, err=%s",
                user.id, update_data, e,
            )
            raise ValueError(
                "Не удалось обновить пользователя (дубликат данных)"
            ) from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception(
                "SQLAlchemyError in update_user: user.id=%s, err=%s", user.id, e
            )
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(
                "Unexpected error in update_user: user.id=%s, err=%s", user.id, e
            )
            raise

        logger.info("update_user: обновлён user.id=%s, поля=%s", user.id, list(update_data))
        return user

    # ---------- SOCIAL LINKS ----------

    async def link_social(
        self,
        db: AsyncSession,
        user: User,
        link_type: SocialNetworkLinkType,
        social_id: int | str,
    ) -> Optional[User]:
        logger.debug(
            "link_social: user.id=%s, link_type=%s, social_id=%r",
            user.id, link_type, social_id,
        )
        try:
            field = self._social_field_map[link_type]
        except KeyError as e:
            logger.error("link_social: неизвестный link_type=%s", link_type)
            raise ValueError(f"Неизвестный тип соцсети: {link_type!r}") from e

        existing = await self.get_user_by_social(db, link_type, social_id)
        if existing is not None and existing.id != user.id:
            logger.warning(
                "link_social: social_id уже занят, link_type=%s, social_id=%r, "
                "existing.id=%s, user.id=%s",
                link_type, social_id, existing.id, user.id,
            )
            raise ValueError(
                f"{link_type.value}={social_id} уже привязан к user.id={existing.id}"
            )

        setattr(user, field, social_id)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in link_social: user.id=%s, link_type=%s, social_id=%r, err=%s",
                user.id, link_type, social_id, e,
            )
            raise ValueError(
                f"Этот {link_type.value} ID уже был привязан другим пользователем"
            ) from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception(
                "SQLAlchemyError in link_social: user.id=%s, err=%s", user.id, e
            )
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(
                "Unexpected error in link_social: user.id=%s, err=%s", user.id, e
            )
            raise

        logger.info(
            "link_social: привязан user.id=%s, link_type=%s, social_id=%r",
            user.id, link_type, social_id,
        )
        return user

    async def unlink_social(
        self,
        db: AsyncSession,
        user: User,
        link_type: SocialNetworkLinkType,
    ) -> Optional[User]:
        logger.debug("unlink_social: user.id=%s, link_type=%s", user.id, link_type)
        try:
            field = self._social_field_map[link_type]
        except KeyError as e:
            logger.error("unlink_social: неизвестный link_type=%s", link_type)
            raise ValueError(f"Неизвестный тип соцсети: {link_type!r}") from e

        setattr(user, field, None)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in unlink_social: user.id=%s, link_type=%s, err=%s",
                user.id, link_type, e,
            )
            raise ValueError(
                "Невозможно отвязать соцсеть (поле не может быть NULL)"
            ) from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception(
                "SQLAlchemyError in unlink_social: user.id=%s, err=%s", user.id, e
            )
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(
                "Unexpected error in unlink_social: user.id=%s, err=%s", user.id, e
            )
            raise

        logger.info("unlink_social: отвязан user.id=%s, link_type=%s", user.id, link_type)
        return user

    async def get_user_by_telegram_id(
        self, db: AsyncSession, telegram_id: int | str
    ) -> Optional[User]:
        return await self.get_user_by_social(
            db, SocialNetworkLinkType.TG_ID, telegram_id
        )

    async def get_user_by_vk_id(
        self, db: AsyncSession, vk_id: int | str
    ) -> Optional[User]:
        return await self.get_user_by_social(db, SocialNetworkLinkType.VK, vk_id)

    async def get_user_by_max_id(
        self, db: AsyncSession, max_id: int | str
    ) -> Optional[User]:
        return await self.get_user_by_social(db, SocialNetworkLinkType.MAX_id, max_id)

    # ---------- DELETE ----------

    async def delete_user(self, db: AsyncSession, user: User) -> bool:
        logger.debug("delete_user: user.id=%s", user.id)
        await db.delete(user)

        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in delete_user: user.id=%s, err=%s", user.id, e
            )
            raise ValueError(
                "Невозможно удалить пользователя: существуют связанные записи"
            ) from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception(
                "SQLAlchemyError in delete_user: user.id=%s, err=%s", user.id, e
            )
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(
                "Unexpected error in delete_user: user.id=%s, err=%s", user.id, e
            )
            raise

        logger.info("delete_user: удалён user.id=%s", user.id)
        return True

    def get_social_field(self, link_type: SocialNetworkLinkType) -> str:
        """Публичный геттер имени поля модели по типу соцсети."""
        try:
            return self._social_field_map[link_type]
        except KeyError as e:
            logger.error("get_social_field: неизвестный link_type=%s", link_type)
            raise ValueError(f"Неизвестный тип соцсети: {link_type!r}") from e


# Готовый синглтон-экземпляр для импорта
user_crud = UserCRUD()