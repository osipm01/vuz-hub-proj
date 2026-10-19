import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotUserService(BaseApiService):
    resource: ClassVar[str] = "/users"

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._list(skip=skip, limit=limit, group_id=group_id)

    async def get_user(self, user_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{user_id}")

    async def get_user_by_email(self, email: str) -> Mapping[str, Any]:
        return await self._api.get(self._path("/by-email"), params={"email": email})

    async def create_user(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_user(self, user_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{user_id}", payload)

    async def delete_user(self, user_id: int) -> None:
        await self._delete(f"/{user_id}")

    async def link_social(
        self, user_id: int, link_type: str, social_id: str
    ) -> Mapping[str, Any]:
        return await self._api.post(
            self._path(f"/{user_id}/social/{link_type}/{social_id}")
        )

    async def unlink_social(self, user_id: int, link_type: str) -> Mapping[str, Any]:
        return await self._api.delete(
            self._path(f"/{user_id}/social/{link_type}"), expect_json=True
        )


user_service: BotUserService = BotUserService()