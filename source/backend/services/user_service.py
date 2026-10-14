# services/user_service.py
# todo убрать лишние _ в названиях не должно быть типа _instane или instane_
# todo добавить более строеую типищацию

import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user_crud import user_crud
from enums.user_enums import SocialNetworkLinkType
from models.models import User
from schemas.user_schema import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:

    _instance: Optional["UserService"] = None
    _initialized: bool = False

    def __new__(cls) -> "UserService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        # зависимость фиксируется один раз — CRUD-синглтон
        self._crud = user_crud
        self.__class__._initialized = True

    # ---------- CREATE ----------

    async def create_user(self, db: AsyncSession, data: UserCreate) -> User:
        """Создаёт пользователя. Проверяет уникальность email перед вставкой."""
        existing = await self._crud.get_user_by_email(db, data.email)
        if existing is not None:
            logger.info(
                "create_user: отказ, email уже занят email=%r existing.id=%s",
                data.email, existing.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Пользователь с email={data.email} уже существует",
            )

        try:
            user = await self._crud.create_user(db, data)
        except Exception as e:
            # CRUD уже залогировал детали, здесь — только HTTP-обёртка
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать пользователя (нарушение целостности данных)",
            ) from e

        logger.info(
            "create_user: успешно создан user.id=%s email=%r", user.id, user.email
        )
        return user

    # ---------- READ ----------

    async def get_user_or_404(self, db: AsyncSession, user_id: int) -> User:
        user = await self._crud.get_user(db, user_id)
        if user is None:
            logger.info("get_user_or_404: не найден user.id=%s", user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        return user

    async def get_user_with_relations_or_404(
        self, db: AsyncSession, user_id: int
    ) -> User:
        user = await self._crud.get_user_with_relations(db, user_id)
        if user is None:
            logger.info(
                "get_user_with_relations_or_404: не найден user.id=%s", user_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )
        return user

    async def list_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
    ) -> Sequence[User]:
        try:
            users = await self._crud.get_users(
                db, skip=skip, limit=limit, group_id=group_id
            )
        except ValueError as e:
            # CRUD сам проверил пагинацию и бросил ValueError
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        logger.info(
            "list_users: count=%d skip=%s limit=%s group_id=%s",
            len(users), skip, limit, group_id,
        )
        return users

    async def get_user_by_social_or_404(
        self,
        db: AsyncSession,
        link_type: SocialNetworkLinkType,
        social_id: int | str,
    ) -> User:
        user = await self._crud.get_user_by_social(db, link_type, social_id)
        if user is None:
            logger.info(
                "get_user_by_social_or_404: не найден link_type=%s social_id=%r",
                link_type, social_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с {link_type.value}={social_id} не найден",
            )
        return user

    # ---------- UPDATE ----------

    async def update_user(
        self, db: AsyncSession, user_id: int, data: UserUpdate
    ) -> User:
        """Обновляет пользователя. Проверяет уникальность email при смене."""
        user = await self.get_user_or_404(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        new_email = update_data.get("email")
        if new_email is not None and new_email != user.email:
            existing = await self._crud.get_user_by_email(db, new_email)
            if existing is not None and existing.id != user.id:
                logger.info(
                    "update_user: отказ, email занят email=%r existing.id=%s user.id=%s",
                    new_email, existing.id, user.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email={new_email} уже используется другим пользователем",
                )

        try:
            updated = await self._crud.update_user(db, user, data)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        if updated is None:
            # По контракту CRUD возвращает Optional[User]; None — «не найден»
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )

        logger.info(
            "update_user: обновлён user.id=%s поля=%s", user_id, list(update_data)
        )
        return updated

    # ---------- SOCIAL LINKS ----------

    async def link_social(
        self,
        db: AsyncSession,
        user_id: int,
        link_type: SocialNetworkLinkType,
        social_id: int | str,
    ) -> User:
        user = await self.get_user_or_404(db, user_id)

        # Предварительная проверка занятости social_id — для корректного HTTP-статуса
        existing = await self._crud.get_user_by_social(db, link_type, social_id)
        if existing is not None and existing.id != user.id:
            logger.info(
                "link_social: отказ, %s=%r уже занят user.id=%s",
                link_type.value, social_id, existing.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{link_type.value}={social_id} уже привязан "
                    f"к другому пользователю"
                ),
            )

        try:
            linked = await self._crud.link_social(db, user, link_type, social_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e

        if linked is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )

        logger.info(
            "link_social: успешно user.id=%s link_type=%s social_id=%r",
            user_id, link_type, social_id,
        )
        return linked

    async def unlink_social(
        self,
        db: AsyncSession,
        user_id: int,
        link_type: SocialNetworkLinkType,
    ) -> User:
        user = await self.get_user_or_404(db, user_id)

        # Публичный геттер вместо обращения к приватному _social_field_map
        try:
            field = self._crud.get_social_field(link_type)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        if getattr(user, field, None) is None:
            logger.info(
                "unlink_social: отказ, у user.id=%s нет привязки link_type=%s",
                user_id, link_type,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"У пользователя нет привязанного {link_type.value}",
            )

        try:
            unlinked = await self._crud.unlink_social(db, user, link_type)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        if unlinked is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )

        logger.info(
            "unlink_social: успешно user.id=%s link_type=%s", user_id, link_type
        )
        return unlinked

    # ---------- DELETE ----------

    async def delete_user(self, db: AsyncSession, user_id: int) -> None:
        user = await self.get_user_or_404(db, user_id)

        try:
            await self._crud.delete_user(db, user)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e

        logger.info("delete_user: успешно удалён user.id=%s", user_id)


# Готовый синглтон-экземпляр для импорта
user_service = UserService()