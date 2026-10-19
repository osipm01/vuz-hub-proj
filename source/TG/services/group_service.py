import logging
from typing import Any, ClassVar, Mapping, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotGroupService(BaseApiService):
    resource: ClassVar[str] = "/groups"

    async def list_groups(self, *, skip: int = 0, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return await self._list(skip=skip, limit=limit)

    async def get_group(self, group_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{group_id}")

    async def get_group_by_name(self, name: str) -> Mapping[str, Any]:
        return await self._api.get(self._path("/by-name"), params={"name": name})

    async def create_group(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_group(self, group_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{group_id}", payload)

    async def delete_group(self, group_id: int) -> None:
        await self._delete(f"/{group_id}")


group_service: BotGroupService = BotGroupService()