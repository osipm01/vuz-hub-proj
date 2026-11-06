import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from schemas.schedule_schema import ScheduleCreate, ScheduleUpdate
from models.models import Schedule

logger = logging.getLogger(__name__)


class ScheduleCRUD:
    _instance: Optional["ScheduleCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "ScheduleCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_schedule(self, db: AsyncSession, data: ScheduleCreate) -> Schedule:
        logger.debug("create_schedule: data=%r", data)
        schedule = Schedule(**data.model_dump())
        db.add(schedule)
        try:
            await db.commit()
            await db.refresh(schedule)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in create_schedule: data=%r err=%s", data, e)
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_schedule: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_schedule: err=%s", e)
            raise
        logger.info("create_schedule: создан schedule.id=%s", schedule.id)
        return schedule

    async def get_schedule(self, db: AsyncSession, schedule_id: int) -> Optional[Schedule]:
        logger.debug("get_schedule: id=%s", schedule_id)
        try:
            result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_schedule: id=%s err=%s", schedule_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_schedule: id=%s err=%s", schedule_id, e)
            raise
        if schedule is None:
            logger.warning("get_schedule: не найдено id=%s", schedule_id)
        return schedule

    async def get_schedule_with_relations(
        self, db: AsyncSession, schedule_id: int
    ) -> Optional[Schedule]:
        logger.debug("get_schedule_with_relations: id=%s", schedule_id)
        stmt = (
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .options(joinedload(Schedule.group), joinedload(Schedule.subject))
        )
        try:
            result = await db.execute(stmt)
            schedule = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_schedule_with_relations: id=%s err=%s",
                schedule_id, e,
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_schedule_with_relations: id=%s err=%s",
                schedule_id, e,
            )
            raise
        return schedule

    async def get_schedules(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        weekday: Optional[int] = None,
    ) -> Sequence[Schedule]:
        logger.debug(
            "get_schedules: skip=%s limit=%s group_id=%s subject_id=%s weekday=%s",
            skip, limit, group_id, subject_id, weekday,
        )
        if skip < 0 or limit <= 0:
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")

        stmt = select(Schedule).order_by(Schedule.id)
        if group_id is not None:
            stmt = stmt.where(Schedule.group_id == group_id)
        if subject_id is not None:
            stmt = stmt.where(Schedule.subject_id == subject_id)
        if weekday is not None:
            stmt = stmt.where(Schedule.weekday == weekday)
        stmt = stmt.offset(skip).limit(limit)

        try:
            result = await db.execute(stmt)
            schedules = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_schedules: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_schedules: err=%s", e)
            raise
        logger.debug("get_schedules: получено %d записей", len(schedules))
        return schedules

    async def update_schedule(
        self, db: AsyncSession, schedule: Schedule, data: ScheduleUpdate
    ) -> Optional[Schedule]:
        logger.debug("update_schedule: schedule.id=%s data=%r", schedule.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)
        try:
            await db.commit()
            await db.refresh(schedule)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in update_schedule: id=%s data=%r err=%s",
                         schedule.id, update_data, e)
            raise ValueError("Не удалось обновить расписание (нарушение целостности)") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in update_schedule: id=%s err=%s", schedule.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in update_schedule: id=%s err=%s", schedule.id, e)
            raise
        logger.info("update_schedule: обновлён schedule.id=%s поля=%s",
                    schedule.id, list(update_data))
        return schedule

    async def delete_schedule(self, db: AsyncSession, schedule: Schedule) -> bool:
        logger.debug("delete_schedule: schedule.id=%s", schedule.id)
        await db.delete(schedule)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_schedule: id=%s err=%s", schedule.id, e)
            raise ValueError("Невозможно удалить расписание: связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_schedule: id=%s err=%s", schedule.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_schedule: id=%s err=%s", schedule.id, e)
            raise
        logger.info("delete_schedule: удалён schedule.id=%s", schedule.id)
        return True


schedule_crud = ScheduleCRUD()