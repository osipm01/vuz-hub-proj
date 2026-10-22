import logging
from typing import Any, ClassVar, Final, Mapping, Optional

import httpx

from config import config
from exceptions import (
    ApiConflictError,
    ApiConnectionError,
    ApiError,
    ApiNotFoundError,
    ApiValidationError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

BOT_HEADER: Final[str] = "x-bot-token"


class ApiClient:
    """Async HTTP-клиент к бэкенду. Singleton."""

    instance: ClassVar[Optional["ApiClient"]] = None
    initialized: ClassVar[bool] = False

    def __new__(cls) -> "ApiClient":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        if self.__class__.initialized:
            return
        self._client = httpx.AsyncClient(
            base_url=config.api_base_url,
            timeout=config.api_timeout,
            headers={
                "Accept": "application/json",
                BOT_HEADER: config.bot_token,
            },
        )
        self.__class__.initialized = True

    async def close(self) -> None:
        await self._client.aclose()

    # ---------- core ----------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        expect_json: bool = True,
    ) -> Any:
        url = path
        logger.debug("API %s %s params=%s", method, url, params)

        try:
            response = await self._client.request(
                method, url, params=params, json=json
            )
        except httpx.TimeoutException as e:
            logger.warning("API timeout: %s %s", method, url)
            raise ApiConnectionError("Таймаут запроса к API") from e
        except httpx.HTTPError as e:
            logger.warning("API network error: %s %s — %s", method, url, e)
            raise ApiConnectionError(f"Ошибка сети: {e}") from e

        if response.status_code >= 400:
            self._raise_for_status(response, method, url)

        if response.status_code == httpx.codes.NO_CONTENT or not expect_json:
            return None

        try:
            return response.json()
        except ValueError as e:
            logger.warning("API bad JSON: %s %s", method, url)
            raise ApiError("Некорректный ответ API (не JSON)", status_code=response.status_code) from e

    def _raise_for_status(
        self, response: httpx.Response, method: str, url: str
    ) -> None:
        status_code = response.status_code
        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        detail: str
        if isinstance(payload, dict):
            detail = str(payload.get("detail", payload))
        else:
            detail = str(payload)

        logger.warning("API %s %s -> %s: %s", method, url, status_code, detail)

        if status_code == httpx.codes.NOT_FOUND:
            raise ApiNotFoundError(detail, status_code=status_code, payload=payload)
        if status_code == httpx.codes.CONFLICT:
            raise ApiConflictError(detail, status_code=status_code, payload=payload)
        if status_code in (httpx.codes.BAD_REQUEST, httpx.codes.UNPROCESSABLE_ENTITY):
            raise ApiValidationError(detail, status_code=status_code, payload=payload)
        raise ApiError(detail, status_code=status_code, payload=payload)

    # ---------- verbs ----------

    async def get(self, path: str, *, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, json: Optional[Any] = None, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._request("POST", path, json=json, params=params)

    async def put(self, path: str, *, json: Optional[Any] = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, *, json: Optional[Any] = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str, *, expect_json: bool = False) -> Any:
        return await self._request("DELETE", path, expect_json=expect_json)


api_client: Final[ApiClient] = ApiClient()