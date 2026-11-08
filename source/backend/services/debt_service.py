#ревью +

import logging
from typing import ClassVar, Final, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.debt_crud import debt_crud
from models.models import Debt
from schemas.debt_schema import DebtCreate, DebtUpdate

logger: Final[logging.Logger] = logging.getLogger(__name__)


class DebtService:
    """Сервис для работы с долгами (singleton)."""

    instance: ClassVar[Optional["DebtService"]] = None
    initialized: ClassVar[bool] = False

    def __new__(cls) -> "DebtService":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        if self.__class__.initialized:
            return
        self.crud = debt_crud
        self.__class__.initialized = True

    async def create_debt(self, db: AsyncSession, data: DebtCreate) -> Debt:
        try:
            debt: Debt = await self.crud.create_debt(db, data)
        except Exception as e:
            logger.exception("create_debt: ошибка при создании долга")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать долг (проверьте user_id и subject_id)",
            ) from e
        logger.info("create_debt: создан debt.id=%s", debt.id)
        return debt

    async def get_debt_or_404(self, db: AsyncSession, debt_id: int) -> Debt:
        debt: Optional[Debt] = await self.crud.get_debt(db, debt_id)
        if debt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        return debt

    async def get_debt_with_relations_or_404(
        self, db: AsyncSession, debt_id: int
    ) -> Debt:
        debt: Optional[Debt] = await self.crud.get_debt_with_relations(db, debt_id)
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
            debts: list[Debt] = await self.crud.get_debts(
                db,
                skip=skip,
                limit=limit,
                user_id=user_id,
                subject_id=subject_id,
                is_resolved=is_resolved,
            )
        except ValueError as e:
            logger.warning("list_debts: некорректные параметры — %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        logger.info("list_debts: count=%d", len(debts))
        return debts

    async def update_debt(
        self, db: AsyncSession, debt_id: int, data: DebtUpdate
    ) -> Debt:
        debt: Debt = await self.get_debt_or_404(db, debt_id)
        try:
            updated: Optional[Debt] = await self.crud.update_debt(db, debt, data)
        except ValueError as e:
            logger.warning("update_debt: ошибка обновления debt.id=%s — %s", debt_id, e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        logger.info("update_debt: обновлён debt.id=%s", debt_id)
        return updated

    async def resolve_debt(self, db: AsyncSession, debt_id: int) -> Debt:
        debt: Debt = await self.get_debt_or_404(db, debt_id)
        if debt.is_resolved:
            logger.info("resolve_debt: долг id=%s уже закрыт", debt_id)
            return debt
        try:
            updated: Optional[Debt] = await self.crud.update_debt(
                db, debt, DebtUpdate(is_resolved=True)
            )
        except ValueError as e:
            logger.warning("resolve_debt: ошибка закрытия debt.id=%s — %s", debt_id, e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Долг id={debt_id} не найден",
            )
        logger.info("resolve_debt: долг id=%s закрыт", debt_id)
        return updated

    async def delete_debt(self, db: AsyncSession, debt_id: int) -> None:
        debt: Debt = await self.get_debt_or_404(db, debt_id)
        try:
            await self.crud.delete_debt(db, debt)
        except ValueError as e:
            logger.warning("delete_debt: конфликт при удалении debt.id=%s — %s", debt_id, e)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        logger.info("delete_debt: удалён debt.id=%s", debt_id)


debt_service: Final[DebtService] = DebtService()