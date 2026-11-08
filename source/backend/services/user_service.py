from __future__ import annotations

import logging
from typing import Final, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user_crud import user_crud
from enums.user_enums import SocialNetworkLinkType, UserRole
from models.models import User
from schemas.user_schema import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:

    def __init__(self) -> None:
        self.crud: Final = user_crud

    # ---------- CREATE ----------

    async def create_user(
        self,
        db: AsyncSession,
        data: UserCreate,
        role: UserRole = UserRole.USER,
    ) -> User:
        existing = await self.crud.get_user_by_email(db, data.email)
        if existing is not None:
            logger.info(
                "create_user: email занят email=%r existing.id=%s",
                data.email, existing.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Пользователь с email={data.email} уже существует",
            )

        try:
            user = await self.crud.create_user(db, data, role=role)
        except Exception as exc:
            logger.exception("create_user: crud упал email=%r", data.email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать пользователя (нарушение целостности данных)",
            ) from exc

        logger.info("create_user: создан user.id=%s email=%r", user.id, user.email)
        return user

    # ---------- READ ----------

    async def get_user_or_404(self, db: AsyncSession, user_id: int) -> User:
        user = await self.crud.get_user(db, user_id)
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
        user = await self.crud.get_user_with_relations(db, user_id)
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
            users = await self.crud.get_users(
                db, skip=skip, limit=limit, group_id=group_id
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        logger.info(
            "list_users: count=%d skip=%s limit=%s group_id=%s",
            len(users), skip, limit, group_id,
        )
        return users

    async def get_user_by_social_or_404(
        self,
        db: AsyncSession,
        link_type: SocialNetworkLinkType,
        social_id: int,
    ) -> User:
        user = await self.crud.get_user_by_social(db, link_type, social_id)
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
        user = await self.get_user_or_404(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        new_email = update_data.get("email")
        if new_email is not None and new_email != user.email:
            existing = await self.crud.get_user_by_email(db, new_email)
            if existing is not None and existing.id != user.id:
                logger.info(
                    "update_user: email занят email=%r existing.id=%s user.id=%s",
                    new_email, existing.id, user.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email={new_email} уже используется другим пользователем",
                )

        try:
            updated = await self.crud.update_user(db, user, data)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        logger.info(
            "update_user: обновлён user.id=%s fields=%s",
            user_id, list(update_data),
        )
        return updated

    async def update_role(
        self, db: AsyncSession, user_id: int, role: UserRole
    ) -> User:
        user = await self.get_user_or_404(db, user_id)
        if user.role == role:
            logger.info(
                "update_role: no-op user.id=%s role уже %s", user_id, role.value
            )
            return user

        try:
            updated = await self.crud.update_role(db, user, role)
        except Exception as exc:
            logger.exception("update_role: crud упал user.id=%s", user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось обновить роль",
            ) from exc

        logger.info("update_role: user.id=%s новая роль=%s", user_id, role.value)
        return updated

    # ---------- SOCIAL LINKS ----------

    async def link_social(
        self,
        db: AsyncSession,
        user_id: int,
        link_type: SocialNetworkLinkType,
        social_id: int,
    ) -> User:
        user = await self.get_user_or_404(db, user_id)

        existing = await self.crud.get_user_by_social(db, link_type, social_id)
        if existing is not None and existing.id != user.id:
            logger.info(
                "link_social: занято %s=%r user.id=%s",
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
            linked = await self.crud.link_social(db, user, link_type, social_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        logger.info(
            "link_social: user.id=%s link_type=%s social_id=%r",
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

        try:
            field = self.crud.get_social_field(link_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        if getattr(user, field, None) is None:
            logger.info(
                "unlink_social: нет привязки user.id=%s link_type=%s",
                user_id, link_type,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"У пользователя нет привязанного {link_type.value}",
            )

        try:
            unlinked = await self.crud.unlink_social(db, user, link_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        logger.info(
            "unlink_social: user.id=%s link_type=%s", user_id, link_type
        )
        return unlinked

    # ---------- DELETE ----------

    async def delete_user(self, db: AsyncSession, user_id: int) -> None:
        user = await self.get_user_or_404(db, user_id)

        try:
            await self.crud.delete_user(db, user)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        logger.info("delete_user: удалён user.id=%s", user_id)

    async def get_user_by_email_or_404(
            self, db: AsyncSession, email: str
    ) -> User:
        user = await self.crud.get_user_by_email(db, email)
        if user is None:
            logger.info("get_user_by_email_or_404: не найден email=%r", email)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с email={email} не найден",
            )
        return user

user_service: Final[UserService] = UserService()