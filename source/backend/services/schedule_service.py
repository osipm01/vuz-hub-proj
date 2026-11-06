# todo убрать лишние _ в названиях не должно быть типа _instane или instane_
# todo добавить более строеую типищацию

#ревью +


import logging
from typing import Any, ClassVar, Optional, Sequence, Self

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.schedule_crud import schedule_crud
from models.models import Schedule
from schemas.schedule_schema import ScheduleCreate, ScheduleUpdate

logger: logging.Logger = logging.getLogger(__name__)


class ScheduleService:
    instance: ClassVar[Optional["ScheduleService"]] = None
    initialized: ClassVar[bool] = False

    def __new__(cls) -> Self:
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        if self.__class__.initialized:
            return
        self.crud = schedule_crud
        self.__class__.initialized = True

    async def create_schedule(self, db: AsyncSession, data: ScheduleCreate) -> Schedule:
        try:
            schedule: Schedule = await self.crud.create_schedule(db, data)
        except IntegrityError as e:
            # Разбираем, какой именно FK не существует (group_id / subject_id),
            # либо какое уникальное ограничение нарушено.
            detail: str = self._build_integrity_error_detail(e, data)
            logger.warning("create_schedule: IntegrityError: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            ) from e
        except Exception as e:
            logger.exception("create_schedule: неожиданная ошибка")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать расписание",
            ) from e
        logger.info("create_schedule: создан schedule.id=%s", schedule.id)
        return schedule

    @staticmethod
    def _build_integrity_error_detail(
        error: IntegrityError, data: ScheduleCreate
    ) -> str:
        text: str = str(error.orig).lower() if error.orig is not None else str(error).lower()

        if "group_id" in text or "group" in text:
            return (
                f"Группа group_id={data.group_id} не существует "
                "или нарушено ограничение по группе"
            )
        if "subject_id" in text or "subject" in text:
            return (
                f"Предмет subject_id={data.subject_id} не существует "
                "или нарушено ограничение по предмету"
            )
        if "unique" in text or "duplicate" in text:
            return "Такая запись расписания уже существует"
        if "foreign key" in text or "fk" in text:
            return "Ссылка на связанную запись не существует (проверьте group_id и subject_id)"
        return "Не удалось создать расписание (нарушение целостности данных)"

    async def get_schedule_or_404(self, db: AsyncSession, schedule_id: int) -> Schedule:
        schedule: Optional[Schedule] = await self.crud.get_schedule(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )
        return schedule

    async def get_schedule_with_relations_or_404(
        self, db: AsyncSession, schedule_id: int
    ) -> Schedule:
        schedule: Optional[Schedule] = await self.crud.get_schedule_with_relations(
            db, schedule_id
        )
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )
        return schedule

    async def list_schedules(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        weekday: Optional[int] = None,
    ) -> Sequence[Schedule]:
        try:
            schedules: Sequence[Schedule] = await self.crud.get_schedules(
                db,
                skip=skip,
                limit=limit,
                group_id=group_id,
                subject_id=subject_id,
                weekday=weekday,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        logger.info("list_schedules: count=%d", len(schedules))
        return schedules

    async def update_schedule(
        self, db: AsyncSession, schedule_id: int, data: ScheduleUpdate
    ) -> Schedule:
        schedule: Schedule = await self.get_schedule_or_404(db, schedule_id)
        try:
            updated: Optional[Schedule] = await self.crud.update_schedule(
                db, schedule, data
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )
        return updated

    async def delete_schedule(self, db: AsyncSession, schedule_id: int) -> None:
        schedule: Schedule = await self.get_schedule_or_404(db, schedule_id)
        try:
            await self.crud.delete_schedule(db, schedule)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        logger.info("delete_schedule: удалено schedule.id=%s", schedule_id)


schedule_service: ScheduleService = ScheduleService()