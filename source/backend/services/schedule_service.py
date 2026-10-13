import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.schedule_crud import schedule_crud
from models.models import Schedule
from schemas.schedule_schema import ScheduleCreate, ScheduleUpdate

logger = logging.getLogger(__name__)


class ScheduleService:
    _instance: Optional["ScheduleService"] = None
    _initialized: bool = False

    def __new__(cls) -> "ScheduleService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = schedule_crud
        self.__class__._initialized = True

    async def create_schedule(self, db: AsyncSession, data: ScheduleCreate) -> Schedule:
        try:
            schedule = await self._crud.create_schedule(db, data)
        except Exception as e:
            # Вероятнее всего FK на group/subject не существует
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать расписание (проверьте group_id и subject_id)",
            ) from e
        logger.info("create_schedule: создан schedule.id=%s", schedule.id)
        return schedule

    async def get_schedule_or_404(self, db: AsyncSession, schedule_id: int) -> Schedule:
        schedule = await self._crud.get_schedule(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )
        return schedule

    async def get_schedule_with_relations_or_404(
        self, db: AsyncSession, schedule_id: int
    ) -> Schedule:
        schedule = await self._crud.get_schedule_with_relations(db, schedule_id)
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
            schedules = await self._crud.get_schedules(
                db, skip=skip, limit=limit,
                group_id=group_id, subject_id=subject_id, weekday=weekday,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_schedules: count=%d", len(schedules))
        return schedules

    async def update_schedule(
        self, db: AsyncSession, schedule_id: int, data: ScheduleUpdate
    ) -> Schedule:
        schedule = await self.get_schedule_or_404(db, schedule_id)
        try:
            updated = await self._crud.update_schedule(db, schedule, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )
        return updated

    async def delete_schedule(self, db: AsyncSession, schedule_id: int) -> None:
        schedule = await self.get_schedule_or_404(db, schedule_id)
        try:
            await self._crud.delete_schedule(db, schedule)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_schedule: удалено schedule.id=%s", schedule_id)


schedule_service = ScheduleService()