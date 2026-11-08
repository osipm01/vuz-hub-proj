import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from schemas.dop_schema import DopCreate, DopUpdate
from models.models import Dop

logger = logging.getLogger(__name__)


class DopCRUD:
    _instance: Optional["DopCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "DopCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_dop(self, db: AsyncSession, data: DopCreate) -> Dop:
        logger.debug("create_dop: data=%r", data)
        dop = Dop(**data.model_dump())
        db.add(dop)
        try:
            await db.commit()
            await db.refresh(dop)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in create_dop: data=%r err=%s", data, e)
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_dop: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_dop: err=%s", e)
            raise
        logger.info("create_dop: создан dop.id=%s user_id=%s", dop.id, dop.user_id)
        return dop

    async def get_dop(self, db: AsyncSession, dop_id: int) -> Optional[Dop]:
        logger.debug("get_dop: id=%s", dop_id)
        try:
            result = await db.execute(select(Dop).where(Dop.id == dop_id))
            dop = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_dop: id=%s err=%s", dop_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_dop: id=%s err=%s", dop_id, e)
            raise
        if dop is None:
            logger.warning("get_dop: не найден id=%s", dop_id)
        return dop

    async def get_dop_with_user(self, db: AsyncSession, dop_id: int) -> Optional[Dop]:
        logger.debug("get_dop_with_user: id=%s", dop_id)
        stmt = select(Dop).where(Dop.id == dop_id).options(joinedload(Dop.user))
        try:
            result = await db.execute(stmt)
            dop = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_dop_with_user: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_dop_with_user: err=%s", e)
            raise
        return dop

    async def get_dops(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
    ) -> Sequence[Dop]:
        logger.debug("get_dops: skip=%s limit=%s user_id=%s", skip, limit, user_id)
        if skip < 0 or limit <= 0:
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")

        stmt = select(Dop).order_by(Dop.id)
        if user_id is not None:
            stmt = stmt.where(Dop.user_id == user_id)
        stmt = stmt.offset(skip).limit(limit)

        try:
            result = await db.execute(stmt)
            dops = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_dops: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_dops: err=%s", e)
            raise
        logger.debug("get_dops: получено %d записей", len(dops))
        return dops

    async def update_dop(
        self, db: AsyncSession, dop: Dop, data: DopUpdate
    ) -> Optional[Dop]:
        logger.debug("update_dop: dop.id=%s data=%r", dop.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(dop, field, value)
        try:
            await db.commit()
            await db.refresh(dop)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in update_dop: id=%s data=%r err=%s",
                         dop.id, update_data, e)
            raise ValueError("Не удалось обновить запись ДОП (нарушение целостности)") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in update_dop: id=%s err=%s", dop.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in update_dop: id=%s err=%s", dop.id, e)
            raise
        logger.info("update_dop: обновлён dop.id=%s поля=%s", dop.id, list(update_data))
        return dop

    async def delete_dop(self, db: AsyncSession, dop: Dop) -> bool:
        logger.debug("delete_dop: dop.id=%s", dop.id)
        await db.delete(dop)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_dop: id=%s err=%s", dop.id, e)
            raise ValueError("Невозможно удалить запись ДОП: связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_dop: id=%s err=%s", dop.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_dop: id=%s err=%s", dop.id, e)
            raise
        logger.info("delete_dop: удалён dop.id=%s", dop.id)
        return True


dop_crud = DopCRUD()