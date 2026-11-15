from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db, get_redis
from drivers.redis import RedisDriver
from schemas.study import ScheduleCreate, ScheduleRead, ScheduleUpdate
from services.study.schedule_service import schedule_service

router = APIRouter()

# Annotated тип для Redis-зависимости
RedisDep = Optional[RedisDriver]


@router.get("/", response_model=list[ScheduleRead], summary="Список расписаний")
async def list_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    group_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    weekday: Optional[int] = Query(None, ge=0, le=6),
    db: AsyncSession = Depends(get_async_db),
    redis: RedisDep = Depends(get_redis),
):
    return await schedule_service.list_schedules(
        db, skip=skip, limit=limit,
        group_id=group_id, subject_id=subject_id, weekday=weekday,
        redis=redis,
    )


@router.get("/{schedule_id}", response_model=ScheduleRead, summary="Расписание по ID (со связями)")
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_async_db),
    redis: RedisDep = Depends(get_redis),
):
    return await schedule_service.get_schedule_with_relations_or_404(
        db, schedule_id, redis=redis,
    )


@router.post("/", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED, summary="Создать расписание")
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_async_db),
    redis: RedisDep = Depends(get_redis),
):
    return await schedule_service.create_schedule(db, data, redis=redis)


@router.put("/{schedule_id}", response_model=ScheduleRead, summary="Обновить расписание")
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: AsyncSession = Depends(get_async_db),
    redis: RedisDep = Depends(get_redis),
):
    return await schedule_service.update_schedule(db, schedule_id, data, redis=redis)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить расписание")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_async_db),
    redis: RedisDep = Depends(get_redis),
):
    await schedule_service.delete_schedule(db, schedule_id, redis=redis)
