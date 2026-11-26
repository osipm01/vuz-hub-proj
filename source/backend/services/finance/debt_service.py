from __future__ import annotations

import logging
from typing import Final, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.finance.debt_crud import debt_crud
from schemas.finance.finance_schema import Debt, DebtCreate, DebtUpdate

logger = logging.getLogger(__name__)


class DebtService:
    """Сервис для работы с долгами."""

    def __init__(self) -> None:
        self.crud: Final = debt_crud

    async def create_debt(self, db: AsyncSession, data: DebtCreate) -> Debt:
        try:
            debt = await self.crud.create_debt(db, data)
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать долг",
            )
        except Exception as e:
            logger.exception("create_debt: непредвиденная ошибка")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать долг",
            ) from e
        logger.info("create_debt: создан debt.id=%s", debt.id)
        return debt

    async def get_debt_or_404(self, db: AsyncSession, debt_id: int) -> Debt:
        debt = await self.crud.get_debt(db, debt_id)
        if debt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        return debt

    async def get_debt_with_relations_or_404(
        self, db: AsyncSession, debt_id: int
    ) -> Debt:
        debt = await self.crud.get_debt_with_relations(db, debt_id)
        if debt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        return debt

    async def list_debts(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        is_resolved: Optional[bool] = None,
    ) -> list[Debt]:
        try:
            debts = await self.crud.get_debts(
                db, skip=skip, limit=limit,
                user_id=user_id, subject_id=subject_id, is_resolved=is_resolved,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_debts: count=%d", len(debts))
        return debts

    async def update_debt(
        self, db: AsyncSession, debt_id: int, data: DebtUpdate
    ) -> Debt:
        debt = await self.get_debt_or_404(db, debt_id)
        try:
            updated = await self.crud.update_debt(db, debt, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось обновить долг",
            )
        logger.info("update_debt: обновлён debt.id=%s", debt_id)
        return updated

    async def resolve_debt(self, db: AsyncSession, debt_id: int) -> Debt:
        debt = await self.get_debt_or_404(db, debt_id)
        if debt.is_resolved:
            logger.info("resolve_debt: долг id=%s уже закрыт", debt_id)
            return debt
        try:
            updated = await self.crud.update_debt(db, debt, DebtUpdate(is_resolved=True))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось закрыть долг",
            )
        logger.info("resolve_debt: долг id=%s закрыт", debt_id)
        return updated

    async def delete_debt(self, db: AsyncSession, debt_id: int) -> None:
        debt = await self.get_debt_or_404(db, debt_id)
        try:
            await self.crud.delete_debt(db, debt)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_debt: удалён debt.id=%s", debt_id)


debt_service: Final[DebtService] = DebtService()
