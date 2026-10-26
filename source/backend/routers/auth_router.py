from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from enums.auth_type_enum import AuthType
from enums.user_enums import SocialNetworkLinkType, UserRole
from guards.role_guard import Principal, get_principal
from schemas.auth_schema import (
    LoginRequest,
    RegisterRequest,
    SocialLoginRequest,
    TokenResponse,
)
from services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Зависимости
DbSession = Annotated[AsyncSession, Depends(get_async_db)]


# ============================================================
# EMAIL / PASSWORD AUTH
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход по email и паролю",
)
async def login(
        data: LoginRequest,
        db: DbSession,
) -> TokenResponse:
    """
    Аутентификация пользователя по email и паролю.
    Возвращает access_token и refresh_token.
    """
    logger.info("login: попытка входа email=%r", data.email)

    tokens = await auth_service.authenticate_by_email(
        db=db,
        email=data.email,
        password=data.password,
    )

    return TokenResponse(**tokens)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(
        data: RegisterRequest,
        db: DbSession,
) -> TokenResponse:
    """
    Регистрация нового пользователя с email и паролем.
    Возвращает access_token и refresh_token.
    """
    logger.info("register: попытка регистрации email=%r", data.email)

    tokens = await auth_service.register_user(
        db=db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
    )

    return TokenResponse(**tokens)


# ============================================================
# SOCIAL AUTH (VK, Telegram, MAX)
# ============================================================

@router.post(
    "/login/social",
    response_model=TokenResponse,
    summary="Вход через социальную сеть",
)
async def login_social(
        data: SocialLoginRequest,
        db: DbSession,
) -> TokenResponse:
    """
    Аутентификация через социальную сеть (VK, Telegram, MAX).
    Если пользователь не найден, автоматически создает нового.
    Возвращает access_token и refresh_token.
    """
    logger.info(
        "login_social: попытка входа link_type=%s social_id=%r",
        data.link_type.value, data.social_id,
    )

    tokens = await auth_service.login_or_register_social(
        db=db,
        link_type=data.link_type,
        social_id=data.social_id,
        email=data.email,
    )

    return TokenResponse(**tokens)


@router.post(
    "/login/vk",
    response_model=TokenResponse,
    summary="Вход через VK",
)
async def login_vk(
        vk_id: int,
        email: str | None = None,
        db: DbSession = None,
) -> TokenResponse:
    """
    Упрощенный вход через VK ID.
    """
    logger.info("login_vk: попытка входа vk_id=%r", vk_id)

    tokens = await auth_service.login_or_register_social(
        db=db,
        link_type=SocialNetworkLinkType.VK,
        social_id=vk_id,
        email=email,
    )

    return TokenResponse(**tokens)


@router.post(
    "/login/telegram",
    response_model=TokenResponse,
    summary="Вход через Telegram",
)
async def login_telegram(
        telegram_id: int,
        email: str | None = None,
        db: DbSession = None,
) -> TokenResponse:
    """
    Упрощенный вход через Telegram ID.
    """
    logger.info("login_telegram: попытка входа telegram_id=%r", telegram_id)

    tokens = await auth_service.login_or_register_social(
        db=db,
        link_type=SocialNetworkLinkType.TG_ID,
        social_id=telegram_id,
        email=email,
    )

    return TokenResponse(**tokens)


@router.post(
    "/login/max",
    response_model=TokenResponse,
    summary="Вход через MAX",
)
async def login_max(
        max_id: int,
        email: str | None = None,
        db: DbSession = None,
) -> TokenResponse:
    """
    Упрощенный вход через MAX ID.
    """
    logger.info("login_max: попытка входа max_id=%r", max_id)

    tokens = await auth_service.login_or_register_social(
        db=db,
        link_type=SocialNetworkLinkType.MAX_id,
        social_id=max_id,
        email=email,
    )

    return TokenResponse(**tokens)


# ============================================================
# LOGOUT (опционально, если используете refresh tokens)
# ============================================================

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход из системы",
)
async def logout(
        principal: Annotated[Principal, Depends(get_principal)],
) -> None:
    """
    Выход из системы.
    Клиент должен удалить токены на своей стороне.
    """
    logger.info("logout: user.id=%s", principal.user_id)
    # Если используете refresh tokens в БД, можно добавить отзыв токена здесь