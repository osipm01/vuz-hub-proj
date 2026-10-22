from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from enums.auth_type_enum import AuthType
from enums.user_enums import SocialNetworkLinkType, UserRole
from guards.role_guard import Principal, get_principal, role_guard
from schemas.user_schema import (
    SocialLinkRequest,
    SocialLinksResponse,
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserUpdate,
    build_social_links,
)
from services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Готовые зависимости
DbSession = Annotated[AsyncSession, Depends(get_async_db)]
AdminOnly = Annotated[
    Principal, Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))
]
AnyAuth = Annotated[Principal, Depends(get_principal)]


# ============================================================
# ME
# ============================================================
@router.get("/me", response_model=UserRead, summary="Текущий пользователь")
async def get_me(
    principal: AnyAuth,
    db: DbSession,
) -> UserRead:
    if principal.kind != "user" or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эндпоинт доступен только пользователям",
        )
    user = await user_service.get_user_or_404(db, principal.user_id)
    return UserRead.model_validate(user)


# ============================================================
# READ (admin)
# ============================================================
@router.get(
    "/",
    response_model=list[UserRead],
    summary="Список пользователей",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def list_users(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    group_id: Optional[int] = Query(None),
) -> list[UserRead]:
    users = await user_service.list_users(
        db, skip=skip, limit=limit, group_id=group_id
    )
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/by-email",
    response_model=UserRead,
    summary="Пользователь по email",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def get_user_by_email(
    email: str,
    db: DbSession,
) -> UserRead:
    user = await user_service.get_user_by_email_or_404(db, email)
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Пользователь по ID (со связями)",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def get_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_db),
) -> UserRead:
    user = await user_service.get_user_with_relations_or_404(db, user_id)
    return UserRead.model_validate(user)


# ============================================================
# CREATE / UPDATE / DELETE (admin)
# ============================================================
@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def create_user(
    data: UserCreate,
    db: DbSession,
) -> UserRead:
    user = await user_service.create_user(db, data)
    return UserRead.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    summary="Обновить пользователя",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def update_user(
    data: UserUpdate,
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> UserRead:
    user = await user_service.update_user(db, user_id, data)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
    summary="Сменить роль пользователя (admin)",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def update_user_role(
    data: UserRoleUpdate,
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> UserRead:
    user = await user_service.update_role(db, user_id, data.role)
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def delete_user(
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> None:
    await user_service.delete_user(db, user_id)


# ============================================================
# SOCIAL LINKS (admin)
# ============================================================
@router.get(
    "/{user_id}/social",
    response_model=SocialLinksResponse,
    summary="Привязанные соцсети пользователя",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def get_social_links(
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> SocialLinksResponse:
    user = await user_service.get_user_or_404(db, user_id)
    return build_social_links(user)


@router.post(
    "/{user_id}/social/link",
    response_model=UserRead,
    summary="Привязать соцсеть",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def link_social(
    data: SocialLinkRequest,
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> UserRead:
    user = await user_service.link_social(
        db, user_id, data.link_type, data.social_id
    )
    return UserRead.model_validate(user)


@router.post(
    "/{user_id}/social/unlink",
    response_model=UserRead,
    summary="Отвязать соцсеть",
    dependencies=[Depends(role_guard([UserRole.ADMIN], {AuthType.CLIENT}))],
)
async def unlink_social(
    link_type: SocialNetworkLinkType,
    db: DbSession,
    user_id: int = Path(..., gt=0),
) -> UserRead:
    user = await user_service.unlink_social(db, user_id, link_type)
    return UserRead.model_validate(user)