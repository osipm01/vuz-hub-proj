from __future__ import annotations

import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.study.schedule_crud import schedule_crud
from drivers.redis import RedisDriver
from schemas.study.study_schema import ScheduleCreate, ScheduleRead, ScheduleUpdate

logger = logging.getLogger(__name__)

# TTL в секундах
DETAIL_TTL = 5 * 60       # 5 минут
LIST_TTL = 10 * 60        # 10 минут

# Ключи
_KEY_DETAIL = "schedule:detail:{schedule_id}"
_KEY_LIST_ALL = "schedule:list:all:{skip}:{limit}"
_KEY_LIST_GROUP = "schedule:list:group:{group_id}:{skip}:{limit}"
_KEY_LIST_SUBJECT = "schedule:list:subject:{subject_id}:{skip}:{limit}"
_KEY_LIST_WEEKDAY = "schedule:list:weekday:{weekday}:{skip}:{limit}"


class ScheduleService:
    """Сервис работы с расписанием. Redis внедряется через методы (DI)."""

    def __init__(self) -> None:
        self.crud = schedule_crud

    # ================================================================ #
    #  Кеш: единый generic-интерфейс
    # ================================================================ #

    @staticmethod
    async def _cache_get(key: str, redis: Optional[RedisDriver]) -> Optional[dict]:
        if redis is None:
            return None
        try:
            result = await redis.get_json(key)
            if result is not None:
                logger.debug("Cache HIT: %s", key)
            return result
        except Exception:
            logger.warning("Cache GET error for key '%s'", key, exc_info=True)
            return None

    @staticmethod
    async def _cache_set(key: str, value: dict, ttl: int, redis: Optional[RedisDriver]) -> None:
        if redis is None:
            return
        try:
            await redis.set_json(key, value, ttl=ttl)
            logger.debug("Cache SET: %s (ttl=%d)", key, ttl)
        except Exception:
            logger.warning("Cache SET error for key '%s'", key, exc_info=True)

    @staticmethod
    async def _cache_get_list(key: str, redis: Optional[RedisDriver]) -> Optional[list[dict]]:
        if redis is None:
            return None
        try:
            result = await redis.get_json(key)
            if result is not None:
                logger.debug("Cache LIST HIT: %s", key)
            return result
        except Exception:
            logger.warning("Cache LIST GET error for key '%s'", key, exc_info=True)
            return None

    @staticmethod
    async def _cache_set_list(key: str, value: list[dict], ttl: int, redis: Optional[RedisDriver]) -> None:
        if redis is None:
            return
        try:
            await redis.set_json(key, value, ttl=ttl)
            logger.debug("Cache LIST SET: %s (ttl=%d)", key, ttl)
        except Exception:
            logger.warning("Cache LIST SET error for key '%s'", key, exc_info=True)

    # ================================================================ #
    #  Инвалидация
    # ================================================================ #

    async def _invalidate_by_ids(
        self,
        group_id: Optional[int],
        subject_id: Optional[int],
        redis: Optional[RedisDriver],
    ) -> None:
        if redis is None or (group_id is None and subject_id is None):
            return
        try:
            keys_to_delete: list[str] = []
            if group_id is not None:
                keys_to_delete.append(_KEY_LIST_GROUP.format(group_id=group_id, skip=0, limit=9999))
            if subject_id is not None:
                keys_to_delete.append(_KEY_LIST_SUBJECT.format(subject_id=subject_id, skip=0, limit=9999))
            keys_to_delete.append(_KEY_LIST_ALL.format(skip=0, limit=9999))
            if keys_to_delete:
                await redis.delete(*keys_to_delete)
        except Exception:
            logger.warning(
                "Cache invalidation error for group_id=%s, subject_id=%s",
                group_id, subject_id, exc_info=True,
            )

    async def _invalidate_schedule_detail(
        self, schedule_id: int, redis: Optional[RedisDriver]
    ) -> None:
        if redis is None:
            return
        try:
            await redis.delete(_KEY_DETAIL.format(schedule_id=schedule_id))
        except Exception:
            logger.warning("Cache invalidation error for schedule_id=%d", schedule_id, exc_info=True)

    async def _invalidate_all_lists(self, redis: Optional[RedisDriver]) -> None:
        """Удалить все list-ключи — без SCAN, по точным шаблонам с (skip=0, limit=9999)."""
        if redis is None:
            return
        try:
            await redis.delete_pattern(_KEY_LIST_GROUP.split(":")[0] + ":*")
            await redis.delete_pattern(_KEY_LIST_SUBJECT.split(":")[0] + ":*")
            await redis.delete_pattern(_KEY_LIST_WEEKDAY.split(":")[0] + ":*")
            await redis.delete_pattern(_KEY_LIST_ALL.split(":")[0] + ":*")
        except Exception:
            logger.warning("Cache full invalidation error", exc_info=True)

    # ================================================================ #
    #  Утилиты
    # ================================================================ #

    @staticmethod
    def _model_dump_schedule(schedule: object) -> dict:
        """Сериализовать объект Schedule в dict для кеша."""
        # Используем inspect чтобы получить все sqlalchemy-атрибуты
        inst = sa_inspect(schedule)
        if inst.attrs is None:
            return {}
        data = {attr.key: getattr(schedule, attr.key, None) for attr in inst.attrs}
        # Форматируем datetime поля
        for key in ("start_time",):
            if key in data and data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    @staticmethod
    def _dict_to_schedule(data: dict) -> dict:
        """Восстановить объект из dict — возвращаем dict (FastAPI/pydantic обработает)."""
        return data

    @staticmethod
    def _build_integrity_error_detail(error: IntegrityError, data: ScheduleCreate) -> str:
        # P1-fix: разбираем constraint_name из orig.diag, не подстроки
        if error.orig is not None and hasattr(error.orig, "diag"):
            constraint = getattr(error.orig.diag, "constraint_name", "") or ""
            # PostgreSQL имена ограничений: uq_schedules_xxx, fk_schedules_xxx
            if "fk_" in constraint or "foreign" in constraint.lower():
                return "Ссылка на связанную запись не существует (проверьте group_id и subject_id)"
            if "uq_" in constraint or "unique" in constraint.lower():
                return "Такая запись расписания уже существует"
        # Fallback: подстроки ошибки
        text = str(error.orig).lower() if error.orig is not None else str(error).lower()
        if "duplicate" in text or "unique" in text:
            return "Такая запись расписания уже существует"
        if "foreign key" in text or "fk_" in text:
            return "Ссылка на связанную запись не существует (проверьте group_id и subject_id)"
        return "Не удалось создать расписание (нарушение целостности данных)"

    # ================================================================ #
    #  CRUD операции с кешированием
    # ================================================================ #

    async def create_schedule(
        self,
        db: AsyncSession,
        data: ScheduleCreate,
        redis: Optional[RedisDriver] = None,
    ) -> ScheduleCreate:
        try:
            schedule = await self.crud.create_schedule(db, data)
        except IntegrityError as e:
            detail = self._build_integrity_error_detail(e, data)
            logger.warning("create_schedule: IntegrityError: %s", e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from e
        except SQLAlchemyError:
            logger.exception("create_schedule: ошибка БД")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать расписание",
            )
        except Exception as e:
            logger.exception("create_schedule: неожиданная ошибка")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось создать расписание"
            ) from e

        await self._invalidate_schedule_detail(schedule.id, redis)
        await self._invalidate_by_ids(group_id=data.group_id, subject_id=data.subject_id, redis=redis)
        await self._invalidate_all_lists(redis)

        logger.info("create_schedule: создан schedule.id=%s", schedule.id)
        return schedule

    async def get_schedule_or_404(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ) -> object:
        cache_key = _KEY_DETAIL.format(schedule_id=schedule_id)
        cached = await self._cache_get(cache_key, redis)
        if cached is not None:
            return self._dict_to_schedule(cached)

        schedule = await self.crud.get_schedule(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        await self._cache_set(cache_key, self._model_dump_schedule(schedule), DETAIL_TTL, redis)
        return schedule

    async def get_schedule_with_relations_or_404(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ) -> object:
        # P0-fix: используем тот же ключ, но сериализуем через get_schedule_with_relations
        cache_key = _KEY_DETAIL.format(schedule_id=schedule_id)
        cached = await self._cache_get(cache_key, redis)
        if cached is not None:
            return self._dict_to_schedule(cached)

        schedule = await self.crud.get_schedule_with_relations(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        # Сериализуем полную запись (с связями, если CRUD их подгрузит)
        await self._cache_set(cache_key, self._model_dump_schedule(schedule), DETAIL_TTL, redis)
        return schedule

    async def list_schedules(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        weekday: Optional[int] = None,
        redis: Optional[RedisDriver] = None,
    ) -> Sequence:
        # P0-fix: ключ из ПОЛНОГО набора параметров (включая skip, limit)
        cache_key: str
        if group_id is not None:
            cache_key = _KEY_LIST_GROUP.format(group_id=group_id, skip=skip, limit=limit)
        elif subject_id is not None:
            cache_key = _KEY_LIST_SUBJECT.format(subject_id=subject_id, skip=skip, limit=limit)
        elif weekday is not None:
            cache_key = _KEY_LIST_WEEKDAY.format(weekday=weekday, skip=skip, limit=limit)
        else:
            cache_key = _KEY_LIST_ALL.format(skip=skip, limit=limit)

        if skip == 0:
            cached = await self._cache_get_list(cache_key, redis)
            if cached is not None:
                # P0-fix: без [::limit], кеш уже содержит нужные данные
                return [ScheduleRead(**item) for item in cached]

        try:
            schedules = await self.crud.get_schedules(
                db, skip=skip, limit=limit, group_id=group_id,
                subject_id=subject_id, weekday=weekday,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        if skip == 0:
            dump_list = [self._model_dump_schedule(s) for s in schedules]
            await self._cache_set_list(cache_key, dump_list, LIST_TTL, redis)

        logger.info("list_schedules: count=%d", len(schedules))
        return schedules

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        data: ScheduleUpdate,
        redis: Optional[RedisDriver] = None,
    ) -> object:
        schedule = await self.get_schedule_or_404(db, schedule_id, redis=redis)
        old_group_id = schedule.group_id  # type: ignore[attr-defined]
        old_subject_id = schedule.subject_id  # type: ignore[attr-defined]

        try:
            updated = await self.crud.update_schedule(db, schedule, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось обновить расписание",
            )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        # P0-fix: инвалидируем деталь + все списки по старым и новым связям
        await self._invalidate_schedule_detail(schedule_id, redis)
        await self._invalidate_by_ids(
            group_id=old_group_id, subject_id=old_subject_id, redis=redis,
        )
        new_group_id = updated.group_id  # type: ignore[attr-defined]
        new_subject_id = updated.subject_id  # type: ignore[attr-defined]
        if new_group_id != old_group_id or new_subject_id != old_subject_id:
            await self._invalidate_by_ids(
                group_id=new_group_id, subject_id=new_subject_id, redis=redis,
            )
        await self._invalidate_all_lists(redis)

        return updated

    async def delete_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ) -> None:
        schedule = await self.get_schedule_or_404(db, schedule_id, redis=redis)
        group_id = schedule.group_id  # type: ignore[attr-defined]
        subject_id = schedule.subject_id  # type: ignore[attr-defined]

        try:
            await self.crud.delete_schedule(db, schedule)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось удалить расписание",
            )

        await self._invalidate_schedule_detail(schedule_id, redis)
        await self._invalidate_by_ids(group_id=group_id, subject_id=subject_id, redis=redis)
        await self._invalidate_all_lists(redis)

        logger.info("delete_schedule: удалено schedule.id=%s", schedule_id)


schedule_service = ScheduleService()
