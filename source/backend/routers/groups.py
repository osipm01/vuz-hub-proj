from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from schemas.group_schema import GroupCreate, GroupRead, GroupUpdate
from services.group_service import group_service

router = APIRouter()


@router.get("/", response_model=list[GroupRead], summary="Список групп")
async def list_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_db),
):
    return await group_service.list_groups(db, skip=skip, limit=limit)


@router.get("/by-name", response_model=GroupRead, summary="Группа по имени")
async def get_group_by_name(name: str, db: AsyncSession = Depends(get_async_db)):
    return await group_service.get_group_by_name_or_404(db, name)


@router.get("/{group_id}", response_model=GroupRead, summary="Группа по ID (со связями)")
async def get_group(group_id: int, db: AsyncSession = Depends(get_async_db)):
    return await group_service.get_group_with_relations_or_404(db, group_id)


@router.post("/", response_model=GroupRead, status_code=status.HTTP_201_CREATED, summary="Создать группу")
async def create_group(data: GroupCreate, db: AsyncSession = Depends(get_async_db)):
    return await group_service.create_group(db, data)


@router.put("/{group_id}", response_model=GroupRead, summary="Обновить группу")
async def update_group(group_id: int, data: GroupUpdate, db: AsyncSession = Depends(get_async_db)):
    return await group_service.update_group(db, group_id, data)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить группу")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_async_db)):
    await group_service.delete_group(db, group_id)