import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from services.base_service import BaseApiService

logger: logging.Logger = logging.getLogger(__name__)


class BotDebtService(BaseApiService):
    resource: ClassVar[str] = "/debts"

    async def list_debts(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        is_resolved: Optional[bool] = None,
    ) -> Sequence[Mapping[str, Any]]:
        return await self._list(
            skip=skip, limit=limit,
            user_id=user_id, subject_id=subject_id, is_resolved=is_resolved,
        )

    async def get_debt(self, debt_id: int) -> Mapping[str, Any]:
        return await self._get_by_path(f"/{debt_id}")

    async def create_debt(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._create(payload)

    async def update_debt(self, debt_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._update(f"/{debt_id}", payload)

    async def resolve_debt(self, debt_id: int) -> Mapping[str, Any]:
        return await self._api.patch(self._path(f"/{debt_id}/resolve"))

    async def delete_debt(self, debt_id: int) -> None:
        await self._delete(f"/{debt_id}")


debt_service: BotDebtService = BotDebtService()