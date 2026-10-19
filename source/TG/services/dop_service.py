import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotDopService(BaseApiService):
    resource: ClassVar[str] = "/dops"

    async def list_dops(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._list(skip=skip, limit=limit, user_id=user_id)

    async def get_dop(self, dop_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{dop_id}")

    async def create_dop(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_dop(self, dop_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{dop_id}", payload)

    async def delete_dop(self, dop_id: int) -> None:
        await self._delete(f"/{dop_id}")


dop_service: BotDopService = BotDopService()