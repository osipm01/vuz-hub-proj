import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotScheduleService(BaseApiService):
    resource: ClassVar[str] = "/schedules"

    async def list_schedules(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        weekday: Optional[int] = None,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._list(
            skip=skip, limit=limit,
            group_id=group_id, subject_id=subject_id, weekday=weekday,
        )

    async def get_schedule(self, schedule_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{schedule_id}")

    async def create_schedule(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_schedule(self, schedule_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{schedule_id}", payload)

    async def delete_schedule(self, schedule_id: int) -> None:
        await self._delete(f"/{schedule_id}")


schedule_service: BotScheduleService = BotScheduleService()