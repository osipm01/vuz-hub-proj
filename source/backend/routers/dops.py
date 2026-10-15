from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from schemas.dop_schema import DopCreate, DopRead, DopUpdate
from services.dop_service import dop_service

router = APIRouter()


@router.get("/", response_model=list[DopRead], summary="Список ДОПов")
async def list_dops(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_async_db),
):
    return await dop_service.list_dops(db, skip=skip, limit=limit, user_id=user_id)


@router.get("/{dop_id}", response_model=DopRead, summary="ДОП по ID (с пользователем)")
async def get_dop(dop_id: int, db: AsyncSession = Depends(get_async_db)):
    return await dop_service.get_dop_with_user_or_404(db, dop_id)


@router.post("/", response_model=DopRead, status_code=status.HTTP_201_CREATED, summary="Создать ДОП")
async def create_dop(data: DopCreate, db: AsyncSession = Depends(get_async_db)):
    return await dop_service.create_dop(db, data)


@router.put("/{dop_id}", response_model=DopRead, summary="Обновить ДОП")
async def update_dop(dop_id: int, data: DopUpdate, db: AsyncSession = Depends(get_async_db)):
    return await dop_service.update_dop(db, dop_id, data)


@router.delete("/{dop_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить ДОП")
async def delete_dop(dop_id: int, db: AsyncSession = Depends(get_async_db)):
    await dop_service.delete_dop(db, dop_id)