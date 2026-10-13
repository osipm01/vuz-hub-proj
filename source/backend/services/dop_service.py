import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.dop_crud import dop_crud
from models.models import Dop
from schemas.dop_schema import DopCreate, DopUpdate

logger = logging.getLogger(__name__)


class DopService:
    _instance: Optional["DopService"] = None
    _initialized: bool = False

    def __new__(cls) -> "DopService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = dop_crud
        self.__class__._initialized = True

    async def create_dop(self, db: AsyncSession, data: DopCreate) -> Dop:
        try:
            dop = await self._crud.create_dop(db, data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать запись ДОП (проверьте user_id)",
            ) from e
        logger.info("create_dop: создан dop.id=%s", dop.id)
        return dop

    async def get_dop_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop = await self._crud.get_dop(db, dop_id)
        if dop is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        return dop

    async def get_dop_with_user_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop = await self._crud.get_dop_with_user(db, dop_id)
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
    ) -> Sequence[Dop]:
        try:
            dops = await self._crud.get_dops(
                db, skip=skip, limit=limit, user_id=user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_dops: count=%d", len(dops))
        return dops

    async def update_dop(
        self, db: AsyncSession, dop_id: int, data: DopUpdate
    ) -> Dop:
        dop = await self.get_dop_or_404(db, dop_id)
        try:
            updated = await self._crud.update_dop(db, dop, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        return updated

    async def delete_dop(self, db: AsyncSession, dop_id: int) -> None:
        dop = await self.get_dop_or_404(db, dop_id)
        try:
            await self._crud.delete_dop(db, dop)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_dop: удалён dop.id=%s", dop_id)


dop_service = DopService()