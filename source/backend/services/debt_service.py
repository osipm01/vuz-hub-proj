# ревью провел +
import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.debt_crud import debt_crud
from models.models import Debt
from schemas.debt_schema import DebtCreate, DebtUpdate

logger = logging.getLogger(__name__)


class DebtService:
    _instance: Optional["DebtService"] = None
    _initialized: bool = False

    def __new__(cls) -> "DebtService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = debt_crud
        self.__class__._initialized = True

    async def create_debt(self, db: AsyncSession, data: DebtCreate) -> Debt:
        try:
            debt = await self._crud.create_debt(db, data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать долг (проверьте user_id и subject_id)",
            ) from e
        logger.info("create_debt: создан debt.id=%s", debt.id)
        return debt

    async def get_debt_or_404(self, db: AsyncSession, debt_id: int) -> Debt:
        debt = await self._crud.get_debt(db, debt_id)
        if debt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        return debt

    async def get_debt_with_relations_or_404(
        self, db: AsyncSession, debt_id: int
    ) -> Debt:
        debt = await self._crud.get_debt_with_relations(db, debt_id)
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
    ) -> Sequence[Debt]:
        try:
            debts = await self._crud.get_debts(
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
            updated = await self._crud.update_debt(db, debt, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        return updated

    async def resolve_debt(self, db: AsyncSession, debt_id: int) -> Debt:
        debt = await self.get_debt_or_404(db, debt_id)
        if debt.is_resolved:
            logger.info("resolve_debt: долг id=%s уже закрыт", debt_id)
            return debt
        try:
            updated = await self._crud.update_debt(db, debt, DebtUpdate(is_resolved=True))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        logger.info("resolve_debt: долг id=%s закрыт", debt_id)
        return updated

    async def delete_debt(self, db: AsyncSession, debt_id: int) -> None:
        debt = await self.get_debt_or_404(db, debt_id)
        try:
            await self._crud.delete_debt(db, debt)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_debt: удалён debt.id=%s", debt_id)


debt_service = DebtService()