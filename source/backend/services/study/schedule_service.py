import logging
from typing import ClassVar, Optional, Sequence, Self

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.study.schedule_crud import schedule_crud
from drivers.redis import RedisDriver
from schemas.study.study_schema import ScheduleCreate, ScheduleUpdate

logger: logging.Logger = logging.getLogger(__name__)

# TTL в секундах
_DETAIL_TTL: int = 5 * 60       # 5 минут
_LIST_TTL: int = 10 * 60        # 10 минут

# Паттерны ключей
_KEY_DETAIL = "schedule:detail:{schedule_id}"
_KEY_LIST_ALL = "schedule:list:all"
_KEY_LIST_GROUP = "schedule:list:group:{group_id}"
_KEY_LIST_SUBJECT = "schedule:list:subject:{subject_id}"
_KEY_LIST_WEEKDAY = "schedule:list:weekday:{weekday}"
_TAG_GROUP = "tags:schedule:group:{group_id}"
_TAG_SUBJECT = "tags:schedule:subject:{subject_id}"


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

    # ================================================================ #
    #  Вспомогательные методы для работы с кешем
    # ================================================================ #

    @staticmethod
    def _model_dump_schedule(schedule) -> dict:
        """Сериализовать объект Schedule в dict (без связей)."""
        data = {
            "id": schedule.id,
            "group_id": schedule.group_id,
            "subject_id": schedule.subject_id,
            "weekday": schedule.weekday,
            "start_time": schedule.start_time.isoformat() if schedule.start_time else None,
            "classroom": schedule.classroom,
        }
        return data

    async def _cache_get(self, key: str, redis: Optional[RedisDriver]) -> Optional[dict]:
        """Получить из кеша, при ошибке Redis — None."""
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

    async def _cache_set(self, key: str, value: dict, ttl: int, redis: Optional[RedisDriver]) -> None:
        """Записать в кеш, при ошибке — молча пропускаем."""
        if redis is None:
            return
        try:
            await redis.set_json(key, value, ttl=ttl)
            logger.debug("Cache SET: %s (ttl=%d)", key, ttl)
        except Exception:
            logger.warning("Cache SET error for key '%s'", key, exc_info=True)

    async def _cache_get_list(self, key: str, redis: Optional[RedisDriver]) -> Optional[list[dict]]:
        """Получить список из кеша."""
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

    async def _cache_set_list(self, key: str, value: list[dict], ttl: int, redis: Optional[RedisDriver]) -> None:
        """Записать список в кеш."""
        if redis is None:
            return
        try:
            await redis.set_json(key, value, ttl=ttl)
            logger.debug("Cache LIST SET: %s (ttl=%d)", key, ttl)
        except Exception:
            logger.warning("Cache LIST SET error for key '%s'", key, exc_info=True)

    async def _invalidate_by_ids(self, group_id: Optional[int], subject_id: Optional[int], redis: Optional[RedisDriver]) -> None:
        """Инвалидировать все кеш-ключи по group_id и subject_id."""
        if redis is None:
            return
        try:
            keys_to_delete: list[str] = []
            tags_to_delete: list[str] = []

            if group_id is not None:
                keys_to_delete.append(_KEY_LIST_GROUP.format(group_id=group_id))
                tags_to_delete.append(_TAG_GROUP.format(group_id=group_id))
            if subject_id is not None:
                keys_to_delete.append(_KEY_LIST_SUBJECT.format(subject_id=subject_id))
                tags_to_delete.append(_TAG_SUBJECT.format(subject_id=subject_id))

            # Удаляем полные списки (пагинация может вернуть другие страницы)
            keys_to_delete.append(_KEY_LIST_ALL)

            if keys_to_delete:
                await redis.delete(*keys_to_delete)
            if tags_to_delete:
                await redis.delete(*tags_to_delete)

            # Также инвалидируем по паттернам (на случай если были запросы с разными фильтрами)
            if group_id is not None:
                pattern = f"schedule:list:group:{group_id}:*"
                await redis.delete_pattern(pattern)
            if subject_id is not None:
                pattern = f"schedule:list:subject:{subject_id}:*"
                await redis.delete_pattern(pattern)

        except Exception:
            logger.warning("Cache invalidation error for group_id=%s, subject_id=%s",
                           group_id, subject_id, exc_info=True)

    async def _invalidate_schedule_detail(self, schedule_id: int, redis: Optional[RedisDriver]) -> None:
        """Инвалидировать детальную запись."""
        if redis is None:
            return
        try:
            await redis.delete(_KEY_DETAIL.format(schedule_id=schedule_id))
        except Exception:
            logger.warning("Cache invalidation error for schedule_id=%d", schedule_id, exc_info=True)

    async def _invalidate_all_schedule_lists(self, redis: Optional[RedisDriver]) -> None:
        """Инвалидировать все списки расписания."""
        if redis is None:
            return
        try:
            # Удаляем по паттернам для всех возможных фильтров
            await redis.delete_pattern("schedule:list:group:*")
            await redis.delete_pattern("schedule:list:subject:*")
            await redis.delete_pattern("schedule:list:weekday:*")
            await redis.delete(_KEY_LIST_ALL)
            await redis.delete_pattern("tags:schedule:*")
        except Exception:
            logger.warning("Cache full invalidation error", exc_info=True)

    # ================================================================ #
    #  CRUD операции с кешированием
    # ================================================================ #

    async def create_schedule(
        self,
        db: AsyncSession,
        data: ScheduleCreate,
        redis: Optional[RedisDriver] = None,
    ):
        try:
            schedule = await self.crud.create_schedule(db, data)
        except IntegrityError as e:
            detail = self._build_integrity_error_detail(e, data)
            logger.warning("create_schedule: IntegrityError: %s", e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from e
        except Exception as e:
            logger.exception("create_schedule: неожиданная ошибка")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось создать расписание") from e

        # Инвалидация кеша
        await self._invalidate_by_ids(
            group_id=data.group_id,
            subject_id=data.subject_id,
            redis=redis,
        )
        await self._invalidate_all_schedule_lists(redis)

        logger.info("create_schedule: создан schedule.id=%s", schedule.id)
        return schedule

    async def get_schedule_or_404(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ):
        # Проверяем кеш
        cache_key = _KEY_DETAIL.format(schedule_id=schedule_id)
        cached = await self._cache_get(cache_key, redis)
        if cached is not None:
            return self._dict_to_schedule(cached)

        # Cache miss — из БД
        schedule = await self.crud.get_schedule(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        # Записываем в кеш
        await self._cache_set(cache_key, self._model_dump_schedule(schedule), _DETAIL_TTL, redis)
        return schedule

    async def get_schedule_with_relations_or_404(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ):
        # Проверяем кеш
        cache_key = _KEY_DETAIL.format(schedule_id=schedule_id)
        cached = await self._cache_get(cache_key, redis)
        if cached is not None:
            return self._dict_to_schedule(cached)

        # Cache miss — из БД
        schedule = await self.crud.get_schedule_with_relations(db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        # Записываем в кеш
        await self._cache_set(cache_key, self._model_dump_schedule(schedule), _DETAIL_TTL, redis)
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
        # Определяем ключ кеша
        cache_key: Optional[str] = None
        if group_id is not None:
            cache_key = _KEY_LIST_GROUP.format(group_id=group_id)
        elif subject_id is not None:
            cache_key = _KEY_LIST_SUBJECT.format(subject_id=subject_id)
        elif weekday is not None:
            cache_key = _KEY_LIST_WEEKDAY.format(weekday=weekday)
        else:
            cache_key = _KEY_LIST_ALL

        # Проверяем кеш (учитываем пагинацию: кешим только первые limit записей)
        if skip == 0:
            cached = await self._cache_get_list(cache_key, redis)
            if cached is not None:
                # Возвращаем с учётом limit (пагинация на уровне кеша)
                return cached[:limit]

        # Cache miss — из БД
        try:
            schedules = await self.crud.get_schedules(
                db, skip=skip, limit=limit, group_id=group_id,
                subject_id=subject_id, weekday=weekday,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        # Записываем в кеш (только если skip==0 — первая страница)
        if skip == 0:
            dump_list = [self._model_dump_schedule(s) for s in schedules]
            await self._cache_set_list(cache_key, dump_list, _LIST_TTL, redis)

        logger.info("list_schedules: count=%d", len(schedules))
        return schedules

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        data: ScheduleUpdate,
        redis: Optional[RedisDriver] = None,
    ):
        # Получаем текущую запись для инвалидации
        schedule = await self.get_schedule_or_404(db, schedule_id, redis=redis)

        old_group_id = schedule.group_id
        old_subject_id = schedule.subject_id

        try:
            updated = await self.crud.update_schedule(db, schedule, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Расписание id={schedule_id} не найдено",
            )

        # Инвалидация кеша
        await self._invalidate_schedule_detail(schedule_id, redis)
        # Инвалидация по старым связям
        await self._invalidate_by_ids(
            group_id=old_group_id,
            subject_id=old_subject_id,
            redis=redis,
        )
        # Инвалидация по новым связям (если изменились)
        new_group_id = updated.group_id
        new_subject_id = updated.subject_id
        if new_group_id != old_group_id or new_subject_id != old_subject_id:
            await self._invalidate_by_ids(
                group_id=new_group_id,
                subject_id=new_subject_id,
                redis=redis,
            )

        return updated

    async def delete_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        redis: Optional[RedisDriver] = None,
    ) -> None:
        # Получаем текущую запись для инвалидации
        schedule = await self.get_schedule_or_404(db, schedule_id, redis=redis)
        group_id = schedule.group_id
        subject_id = schedule.subject_id

        try:
            await self.crud.delete_schedule(db, schedule)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

        # Инвалидация кеша
        await self._invalidate_schedule_detail(schedule_id, redis)
        await self._invalidate_by_ids(
            group_id=group_id,
            subject_id=subject_id,
            redis=redis,
        )
        await self._invalidate_all_schedule_lists(redis)

        logger.info("delete_schedule: удалено schedule.id=%s", schedule_id)

    # ================================================================ #
    #  Утилиты
    # ================================================================ #

    @staticmethod
    def _build_integrity_error_detail(error: IntegrityError, data: ScheduleCreate) -> str:
        text = str(error.orig).lower() if error.orig is not None else str(error).lower()
        if "group_id" in text or "group" in text:
            return f"Группа group_id={data.group_id} не существует или нарушено ограничение по группе"
        if "subject_id" in text or "subject" in text:
            return f"Предмет subject_id={data.subject_id} не существует или нарушено ограничение по предмету"
        if "unique" in text or "duplicate" in text:
            return "Такая запись расписания уже существует"
        if "foreign key" in text or "fk" in text:
            return "Ссылка на связанную запись не существует (проверьте group_id и subject_id)"
        return "Не удалось создать расписание (нарушение целостности данных)"

    @staticmethod
    def _dict_to_schedule(data: dict):
        """Восстановить объект из dict (возвращаем dict, FastAPI/pydantic обработает)."""
        return data


schedule_service = ScheduleService()
