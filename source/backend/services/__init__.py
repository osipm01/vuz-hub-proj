"""Пакет сервисов — точка входа для DI и тестирования."""

from services.auth import (
    auth_service,
    jwt_service,
    token_service,
    user_service,
)
from services.finance import debt_service, dop_service
from services.study import (
    group_service,
    schedule_service,
    subject_service,
    user_subject_service,
)

__all__ = [
    "auth_service",
    "debt_service",
    "dop_service",
    "group_service",
    "jwt_service",
    "schedule_service",
    "subject_service",
    "token_service",
    "user_service",
    "user_subject_service",
]
