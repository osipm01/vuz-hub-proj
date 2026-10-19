import logging
from typing import Any, ClassVar, Mapping, Optional, Sequence

from api_client import api_client
from exceptions import ApiError

logger: logging.Logger = logging.getLogger(__name__)


class BaseApiService:
    """Базовый сервис-обёртка над ApiClient с логом и хелперами."""

    resource: ClassVar[str] = ""  # например, "/users"

    def __init__(self) -> None:
        self._api = api_client

    # ---------- helpers ----------

    def _path(self, suffix: str = "") -> str:
        return f"{self.resource}{suffix}"

    @staticmethod
    def _clean_params(**params: Any) -> dict[str, Any]:
        """Убирает None из query-параметров."""
        return {k: v for k, v in params.items() if v is not None}

    async def _list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> Sequence[Mapping[str, Any]]:
        params = {"skip": skip, "limit": limit, **self._clean_params(**filters)}
        return await self._api.get(self._path("/"), params=params)

    async def _get_by_path(self, suffix: str) -> Mapping[str, Any]:
        return await self._api.get(self._path(suffix))

    async def _create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._api.post(self._path("/"), json=payload)

    async def _update(self, suffix: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._api.put(self._path(suffix), json=payload)

    async def _delete(self, suffix: str) -> None:
        await self._api.delete(self._path(suffix), expect_json=False)

    # ---------- generic error wrapper ----------

    async def safe(self, coro_factory, *args, **kwargs):
        """Утилита: выполнить операцию, вернуть (result, error) для удобства в хендлерах."""
        try:
            return await coro_factory(*args, **kwargs), None
        except ApiError as e:
            logger.info("API error in %s: %s", coro_factory.__name__, e)
            return None, e