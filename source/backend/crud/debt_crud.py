# ревью провел +
import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from schemas.debt_schema import DebtCreate, DebtUpdate
from models.models import Debt

logger = logging.getLogger(__name__)


class DebtCRUD:
    _instance: Optional["DebtCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "DebtCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_debt(self, db: AsyncSession, data: DebtCreate) -> Debt:
        logger.debug("create_debt: data=%r", data)
        debt = Debt(**data.model_dump())
        db.add(debt)
        try:
            await db.commit()
            await db.refresh(debt)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in create_debt: data=%r err=%s", data, e)
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_debt: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_debt: err=%s", e)
            raise
        logger.info("create_debt: создан debt.id=%s user_id=%s", debt.id, debt.user_id)
        return debt

    async def get_debt(self, db: AsyncSession, debt_id: int) -> Optional[Debt]:
        logger.debug("get_debt: id=%s", debt_id)
        try:
            result = await db.execute(select(Debt).where(Debt.id == debt_id))
            debt = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_debt: id=%s err=%s", debt_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_debt: id=%s err=%s", debt_id, e)
            raise
        if debt is None:
            logger.warning("get_debt: не найден id=%s", debt_id)
        return debt

    async def get_debt_with_relations(
        self, db: AsyncSession, debt_id: int
    ) -> Optional[Debt]:
        logger.debug("get_debt_with_relations: id=%s", debt_id)
        stmt = (
            select(Debt)
            .where(Debt.id == debt_id)
            .options(joinedload(Debt.user), joinedload(Debt.subject))
        )
        try:
            result = await db.execute(stmt)
            debt = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_debt_with_relations: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_debt_with_relations: err=%s", e)
            raise
        return debt

    async def get_debts(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        is_resolved: Optional[bool] = None,
    ) -> Sequence[Debt]:
        logger.debug(
            "get_debts: skip=%s limit=%s user_id=%s subject_id=%s is_resolved=%s",
            skip, limit, user_id, subject_id, is_resolved,
        )
        if skip < 0 or limit <= 0:
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")

        stmt = select(Debt).order_by(Debt.id)
        if user_id is not None:
            stmt = stmt.where(Debt.user_id == user_id)
        if subject_id is not None:
            stmt = stmt.where(Debt.subject_id == subject_id)
        if is_resolved is not None:
            stmt = stmt.where(Debt.is_resolved == is_resolved)
        stmt = stmt.offset(skip).limit(limit)

        try:
            result = await db.execute(stmt)
            debts = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_debts: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_debts: err=%s", e)
            raise
        logger.debug("get_debts: получено %d записей", len(debts))
        return debts

    async def update_debt(
        self, db: AsyncSession, debt: Debt, data: DebtUpdate
    ) -> Optional[Debt]:
        logger.debug("update_debt: debt.id=%s data=%r", debt.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(debt, field, value)
        try:
            await db.commit()
            await db.refresh(debt)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in update_debt: id=%s data=%r err=%s",
                         debt.id, update_data, e)
            raise ValueError("Не удалось обновить долг (нарушение целостности)") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in update_debt: id=%s err=%s", debt.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in update_debt: id=%s err=%s", debt.id, e)
            raise
        logger.info("update_debt: обновлён debt.id=%s поля=%s", debt.id, list(update_data))
        return debt

    async def delete_debt(self, db: AsyncSession, debt: Debt) -> bool:
        logger.debug("delete_debt: debt.id=%s", debt.id)
        await db.delete(debt)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_debt: id=%s err=%s", debt.id, e)
            raise ValueError("Невозможно удалить долг: связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_debt: id=%s err=%s", debt.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_debt: id=%s err=%s", debt.id, e)
            raise
        logger.info("delete_debt: удалён debt.id=%s", debt.id)
        return True


debt_crud = DebtCRUD()