from __future__ import annotations

import logging
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user_crud import user_crud
from enums.user_enums import SocialNetworkLinkType, UserRole
from schemas.user_schema import UserCreate
from services.jwt_service import jwt_service

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис бизнес-логики аутентификации и управления сессиями."""

    def __init__(self) -> None:
        self.crud: Final = user_crud
        self.jwt: Final = jwt_service

    # ---------- EMAIL AUTHENTICATION ----------

    async def authenticate_by_email(
            self, db: AsyncSession, email: str, password: str
    ) -> dict[str, str | int]:
        """
        Проверяет email и пароль. Возвращает данные для ответа или выбрасывает 401.
        Сообщение об ошибке намеренно одинаковое для защиты от User Enumeration.
        """
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
            "role": user.role.value,
        }

    # ---------- SOCIAL AUTHENTICATION & REGISTRATION ----------

    async def login_or_register_social(
            self,
            db: AsyncSession,
            link_type: SocialNetworkLinkType,
            social_id: int,
            email: str | None = None,
    ) -> dict[str, str | int | bool]:
        """
        Вход через соцсеть. Если пользователя нет, создает его автоматически.
        """
        logger.debug(
            "login_or_register_social: link_type=%s social_id=%r", link_type, social_id
        )

        user = await self.crud.get_user_by_social(db, link_type, social_id)
        is_new_user = False

        if user is None:
            is_new_user = True
            logger.info(
                "login_or_register_social: регистрация нового через %s social_id=%r",
                link_type.value, social_id,
            )

            social_field = self.crud.get_social_field(link_type)
            # Если соцсеть не отдала email, создаем уникальный placeholder
            safe_email = email or f"social_{link_type.value}_{social_id}@local.placeholder"

            create_data = {
                social_field: social_id,
                "email": safe_email,
                "role": UserRole.USER.value,
            }

            try:
                user = await self.crud.create_user(
                    db, data=UserCreate(**create_data), role=UserRole.USER
                )
            except Exception as exc:
                logger.exception("login_or_register_social: crud упал при создании social_id=%r", social_id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось зарегистрировать пользователя через социальную сеть",
                ) from exc

        access_token = self.jwt.create_access_token(user_id=user.id, role=user.role)
        refresh_token = self.jwt.create_refresh_token(user_id=user.id)

        logger.info(
            "login_or_register_social: выдан токен user.id=%s is_new=%s", user.id, is_new_user
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "is_new_user": is_new_user,
        }

    # ---------- API KEY MANAGEMENT ----------

    async def generate_user_api_key(self, db: AsyncSession, user_id: int) -> str:
        """Генерирует и (опционально) сохраняет API-ключ для пользователя."""
        user = await self.crud.get_user(db, user_id)
        if user is None:
            logger.info("generate_user_api_key: не найден user.id=%s", user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь id={user_id} не найден",
            )

        # Генерация ключа
        api_key = self.jwt.generate_api_key()

        # TODO: Здесь можно добавить сохранение хеша api_key в БД через self.crud,
        # если ваша модель User поддерживает хранение api_keys.

        logger.info("generate_user_api_key: сгенерирован ключ для user.id=%s", user_id)
        return api_key


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

        # ✅ name обязателен; full_name либо email как fallback
        create_data = {
            "email": email,
            "name": full_name or email.split("@")[0],
            "password": hashed_password,  # ✅ имя поля как в модели
            "role": UserRole.USER.value,
        }

        try:
            user = await self.crud.create_user(
                db, data=UserCreate(**create_data), role=UserRole.USER,
            )
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
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        }

    async def authenticate_by_email(
            self, db: AsyncSession, email: str, password: str
    ) -> dict[str, str | int]:
        logger.debug("authenticate_by_email: попытка входа email=%r", email)

        user = await self.crud.get_user_by_email(db, email=email)

        # ✅ .password вместо .hashed_password
        if user is None or not user.password:
            logger.warning("authenticate_by_email: пользователь не найден/без пароля email=%r", email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not self.jwt.verify_password(password, user.password):
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
            "role": user.role.value,
        }


auth_service: Final[AuthService] = AuthService()