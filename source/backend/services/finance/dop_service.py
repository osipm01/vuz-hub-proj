from __future__ import annotations

import logging
from typing import Final, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.finance.dop_crud import dop_crud
from models.finance import Dop
from schemas.finance.finance_schema import DopCreate, DopUpdate

logger = logging.getLogger(__name__)


class DopService:
    """Сервис для работы с записями ДОП."""

    def __init__(self) -> None:
        self.crud: Final = dop_crud

    async def create_dop(self, db: AsyncSession, data: DopCreate) -> Dop:
        try:
            dop = await self.crud.create_dop(db, data)
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать запись ДОП",
            )
        except Exception as e:
            logger.exception("create_dop: непредвиденная ошибка")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать запись ДОП",
            ) from e
        logger.info("create_dop: создан dop.id=%s", dop.id)
        return dop

    async def get_dop_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop = await self.crud.get_dop(db, dop_id)
        if dop is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        return dop

    async def get_dop_with_user_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop = await self.crud.get_dop_with_user(db, dop_id)
        if dop is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        return dop

    async def list_dops(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
    ) -> list[Dop]:
        try:
            dops = await self.crud.get_dops(db, skip=skip, limit=limit, user_id=user_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_dops: count=%d", len(dops))
        return dops

    async def update_dop(
        self, db: AsyncSession, dop_id: int, data: DopUpdate
    ) -> Dop:
        dop = await self.get_dop_or_404(db, dop_id)
        try:
            updated = await self.crud.update_dop(db, dop, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось обновить запись ДОП",
            )
        logger.info("update_dop: обновлён dop.id=%s", dop_id)
        return updated

    async def delete_dop(self, db: AsyncSession, dop_id: int) -> None:
        dop = await self.get_dop_or_404(db, dop_id)
        try:
            await self.crud.delete_dop(db, dop)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_dop: удалён dop.id=%s", dop_id)


dop_service: Final[DopService] = DopService()
