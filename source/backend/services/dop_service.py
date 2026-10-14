#ревью +
import logging
from typing import ClassVar, Final, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.dop_crud import dop_crud
from models.models import Dop
from schemas.dop_schema import DopCreate, DopUpdate

logger: Final[logging.Logger] = logging.getLogger(__name__)


class DopService:
    """Сервис для работы с записями ДОП (singleton)."""

    instance: ClassVar[Optional["DopService"]] = None
    initialized: ClassVar[bool] = False

    def __new__(cls) -> "DopService":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        if self.__class__.initialized:
            return
        self.crud = dop_crud
        self.__class__.initialized = True

    async def create_dop(self, db: AsyncSession, data: DopCreate) -> Dop:
        try:
            dop: Dop = await self.crud.create_dop(db, data)
        except Exception as e:
            logger.exception("create_dop: ошибка при создании записи ДОП")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать запись ДОП (проверьте user_id)",
            ) from e
        logger.info("create_dop: создан dop.id=%s", dop.id)
        return dop

    async def get_dop_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop: Optional[Dop] = await self.crud.get_dop(db, dop_id)
        if dop is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        return dop

    async def get_dop_with_user_or_404(self, db: AsyncSession, dop_id: int) -> Dop:
        dop: Optional[Dop] = await self.crud.get_dop_with_user(db, dop_id)
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
            dops: list[Dop] = await self.crud.get_dops(
                db, skip=skip, limit=limit, user_id=user_id
            )
        except ValueError as e:
            logger.warning("list_dops: некорректные параметры — %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        logger.info("list_dops: count=%d", len(dops))
        return dops

    async def update_dop(
        self, db: AsyncSession, dop_id: int, data: DopUpdate
    ) -> Dop:
        dop: Dop = await self.get_dop_or_404(db, dop_id)
        try:
            updated: Optional[Dop] = await self.crud.update_dop(db, dop, data)
        except ValueError as e:
            logger.warning("update_dop: ошибка обновления dop.id=%s — %s", dop_id, e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись ДОП id={dop_id} не найдена",
            )
        logger.info("update_dop: обновлён dop.id=%s", dop_id)
        return updated

    async def delete_dop(self, db: AsyncSession, dop_id: int) -> None:
        dop: Dop = await self.get_dop_or_404(db, dop_id)
        try:
            await self.crud.delete_dop(db, dop)
        except ValueError as e:
            logger.warning("delete_dop: конфликт при удалении dop.id=%s — %s", dop_id, e)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        logger.info("delete_dop: удалён dop.id=%s", dop_id)


dop_service: Final[DopService] = DopService()