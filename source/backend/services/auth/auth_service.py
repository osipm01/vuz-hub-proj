from __future__ import annotations

import logging
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.auth.user_crud import user_crud
from enums.user_enums import SocialNetworkLinkType, UserRole
from schemas.auth.user_schema import UserCreate
from services.auth.jwt_service import jwt_service

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис бизнес-логики аутентификации и управления сессиями."""

    def __init__(self) -> None:
        self.crud: Final = user_crud
        self.jwt: Final = jwt_service

    async def authenticate_by_email(
            self, db: AsyncSession, email: str, password: str
    ) -> dict[str, str | int]:
        logger.debug("authenticate_by_email: попытка входа email=%r", email)
        user = await self.crud.get_user_by_email(db, email=email)
        if user is None or not user.hashed_password:
            logger.warning("authenticate_by_email: пользователь не найден или без пароля email=%r", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not self.jwt.verify_password(password, user.hashed_password):
            logger.warning("authenticate_by_email: неверный пароль email=%r", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = self.jwt.create_access_token(user_id=user.id, role=user.role)
        refresh_token = self.jwt.create_refresh_token(user_id=user.id)
        logger.info("authenticate_by_email: успешный вход user.id=%s", user.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role_enum.value,
        }

    async def login_or_register_social(
            self,
            db: AsyncSession,
            link_type: SocialNetworkLinkType,
            social_id: int,
            email: str | None = None,
    ) -> dict[str, str | int | bool]:
        logger.debug("login_or_register_social: link_type=%s social_id=%r", link_type, social_id)
        user = await self.crud.get_user_by_social(db, link_type, social_id)
        is_new_user = False
        if user is None:
            is_new_user = True
            logger.info("login_or_register_social: регистрация нового через %s social_id=%r", link_type.value, social_id)
            social_field = self.crud.get_social_field(link_type)
            safe_email = email or f"social_{link_type.value}_{social_id}@local.placeholder"
            create_data = {
                social_field: social_id,
                "email": safe_email,
                "role": UserRole.USER.value,
            }
            try:
                user = await self.crud.create_user(db, data=UserCreate(**create_data), role=UserRole.USER)
            except Exception as exc:
                logger.exception("login_or_register_social: crud упал при создании social_id=%r", social_id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось зарегистрировать пользователя через социальную сеть",
                ) from exc
        access_token = self.jwt.create_access_token(user_id=user.id, role=user.role)
        refresh_token = self.jwt.create_refresh_token(user_id=user.id)
        logger.info("login_or_register_social: выдан токен user.id=%s is_new=%s", user.id, is_new_user)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role_enum.value,
            "is_new_user": is_new_user,
        }

    async def register_user(
            self,
            db: AsyncSession,
            email: str,
            password: str,
            full_name: str | None = None,
    ) -> dict[str, str | int]:
        logger.debug("register_user: попытка регистрации email=%r", email)
        existing = await self.crud.get_user_by_email(db, email=email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Пользователь с email={email} уже существует",
            )
        hashed_password = self.jwt.hash_password(password)
        create_data = {
            "email": email,
            "name": full_name or email.split("@")[0],
            "password": hashed_password,
            "role": UserRole.USER.value,
        }
        try:
            user = await self.crud.create_user(db, data=UserCreate(**create_data), role=UserRole.USER)
        except Exception as exc:
            logger.exception("register_user: crud упал email=%r", email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось зарегистрировать пользователя",
            ) from exc
        access_token = self.jwt.create_access_token(user_id=user.id, role=user.role)
        refresh_token = self.jwt.create_refresh_token(user_id=user.id)
        logger.info("register_user: создан user.id=%s email=%r", user.id, email)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role_enum.value,
        }


auth_service: Final[AuthService] = AuthService()
