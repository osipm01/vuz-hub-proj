from typing import Any, Optional


class ApiError(Exception):
    """Базовая ошибка клиента API."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        payload: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ApiConnectionError(ApiError):
    """Сеть недоступна / таймаут."""


class ApiNotFoundError(ApiError):
    """404."""


class ApiConflictError(ApiError):
    """409."""


class ApiValidationError(ApiError):
    """400 / 422."""