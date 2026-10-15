from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from schemas.debt_schema import DebtCreate, DebtRead, DebtUpdate
from services.debt_service import debt_service

router = APIRouter()


@router.get("/", response_model=list[DebtRead], summary="Список долгов")
async def list_debts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    is_resolved: Optional[bool] = None,
    db: AsyncSession = Depends(get_async_db),
):
    return await debt_service.list_debts(
        db, skip=skip, limit=limit,
        user_id=user_id, subject_id=subject_id, is_resolved=is_resolved,
    )


@router.get("/{debt_id}", response_model=DebtRead, summary="Долг по ID (со связями)")
async def get_debt(debt_id: int, db: AsyncSession = Depends(get_async_db)):
    return await debt_service.get_debt_with_relations_or_404(db, debt_id)


@router.post("/", response_model=DebtRead, status_code=status.HTTP_201_CREATED, summary="Создать долг")
async def create_debt(data: DebtCreate, db: AsyncSession = Depends(get_async_db)):
    return await debt_service.create_debt(db, data)


@router.put("/{debt_id}", response_model=DebtRead, summary="Обновить долг")
async def update_debt(debt_id: int, data: DebtUpdate, db: AsyncSession = Depends(get_async_db)):
    return await debt_service.update_debt(db, debt_id, data)


@router.patch("/{debt_id}/resolve", response_model=DebtRead, summary="Закрыть (resolve) долг")
async def resolve_debt(debt_id: int, db: AsyncSession = Depends(get_async_db)):
    return await debt_service.resolve_debt(db, debt_id)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить долг")
async def delete_debt(debt_id: int, db: AsyncSession = Depends(get_async_db)):
    await debt_service.delete_debt(db, debt_id)