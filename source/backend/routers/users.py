from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from enums.user_enums import SocialNetworkLinkType
from schemas.user_schema import UserCreate, UserRead, UserUpdate
from services.user_service import user_service

router = APIRouter()


@router.get("/", response_model=list[UserRead], summary="Список пользователей")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    group_id: Optional[int] = None,
    db: AsyncSession = Depends(get_async_db),
):
    return await user_service.list_users(db, skip=skip, limit=limit, group_id=group_id)


@router.get("/by-email", response_model=UserRead, summary="Пользователь по email")
async def get_user_by_email(email: str, db: AsyncSession = Depends(get_async_db)):
    return await user_service.get_user_by_email_or_404(db, email)


@router.get("/{user_id}", response_model=UserRead, summary="Пользователь по ID (со связями)")
async def get_user(user_id: int, db: AsyncSession = Depends(get_async_db)):
    return await user_service.get_user_with_relations_or_404(db, user_id)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Создать пользователя")
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_async_db)):
    return await user_service.create_user(db, data)


@router.put("/{user_id}", response_model=UserRead, summary="Обновить пользователя")
async def update_user(user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_async_db)):
    return await user_service.update_user(db, user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить пользователя")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_async_db)):
    await user_service.delete_user(db, user_id)


@router.post("/{user_id}/social/{link_type}/{social_id}", response_model=UserRead,
             summary="Привязать соцсеть")
async def link_social(
    user_id: int,
    link_type: SocialNetworkLinkType,
    social_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    return await user_service.link_social(db, user_id, link_type, social_id)


@router.delete("/{user_id}/social/{link_type}", response_model=UserRead,
               summary="Отвязать соцсеть")
async def unlink_social(
    user_id: int,
    link_type: SocialNetworkLinkType,
    db: AsyncSession = Depends(get_async_db),
):
    return await user_service.unlink_social(db, user_id, link_type)