from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from enums.auth_type_enum import AuthType
from enums.user_enums import UserRole
from guards.role_guard import Principal, role_guard
from schemas.integration import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationTokenRead,
    IntegrationUpdate,
)
from services.auth.token_service import token_service

router = APIRouter()

# ============================================================
# ТОКЕНЫ / КЛЮЧИ ИНТЕГРАЦИИ
# ============================================================

@router.post(
    "/{integration_id}/token",
    response_model=IntegrationTokenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Выпустить JWT-токен для интеграции",
)
async def issue_integration_token(
    integration_id: int,
    db: AsyncSession = Depends(get_async_db),
    principal: Principal = Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT})),
):
    # TODO: добавить сервис для интеграций
    return IntegrationTokenRead(
        integration_id=integration_id,
        token="TODO: implement integration service",
        token_type="bearer",
    )


@router.post(
    "/{integration_id}/api-key",
    response_model=IntegrationTokenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Выпустить opaque API-ключ для интеграции",
)
async def issue_integration_api_key(
    integration_id: int,
    db: AsyncSession = Depends(get_async_db),
    principal: Principal = Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT})),
):
    api_key = token_service.generate_api_key(prefix="int_live_")
    return IntegrationTokenRead(
        integration_id=integration_id,
        token=api_key,
        token_type="api_key",
    )


@router.post(
    "/{integration_id}/rotate",
    response_model=IntegrationTokenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ротация ключа/токена интеграции",
)
async def rotate_integration_credentials(
    integration_id: int,
    kind: str = Query("api_key", pattern="^(api_key|jwt)$"),
    db: AsyncSession = Depends(get_async_db),
    principal: Principal = Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT})),
):
    if kind == "jwt":
        return IntegrationTokenRead(
            integration_id=integration_id,
            token="TODO: implement integration service",
            token_type="bearer",
        )
    api_key = token_service.generate_api_key(prefix="int_live_")
    return IntegrationTokenRead(
        integration_id=integration_id,
        token=api_key,
        token_type="api_key",
    )
