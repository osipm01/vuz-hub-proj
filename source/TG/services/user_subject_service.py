import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotUserSubjectService(BaseApiService):
    resource: ClassVar[str] = "/user-subjects"

    async def list_links(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._list(skip=skip, limit=limit, user_id=user_id, subject_id=subject_id)

    async def get_link(self, user_id: int, subject_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{user_id}/{subject_id}")

    async def create_link(self, user_id: int, subject_id: int) -> Mapping[str, Any]:
        payload = {"user_id": user_id, "subject_id": subject_id}
        return await self._create(payload)

    async def delete_link(self, user_id: int, subject_id: int) -> None:
        await self._delete(f"/{user_id}/{subject_id}")


user_subject_service: BotUserSubjectService = BotUserSubjectService()