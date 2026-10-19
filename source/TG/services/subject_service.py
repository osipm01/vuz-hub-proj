import logging
from typing import Any, ClassVar, Mapping, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotSubjectService(BaseApiService):
    resource: ClassVar[str] = "/subjects"

    async def list_subjects(self, *, skip: int = 0, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return await self._list(skip=skip, limit=limit)

    async def get_subject(self, subject_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{subject_id}")

    async def get_subject_by_name(self, name: str) -> Mapping[str, Any]:
        return await self._api.get(self._path("/by-name"), params={"name": name})

    async def create_subject(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_subject(self, subject_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{subject_id}", payload)

    async def delete_subject(self, subject_id: int) -> None:
        await self._delete(f"/{subject_id}")


subject_service: BotSubjectService = BotSubjectService()