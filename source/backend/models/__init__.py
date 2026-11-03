"""Модели PostgreSQL для всех сервисов VuzHub."""

from .auth import Base as auth_base, User
from .study import Base as study_base, Group, Subject, Schedule, UserSubject
from .finance import Base as finance_base, Debt, Dop
from .integration import Base as integration_base, IntegrationLog, IntegrationToken

__all__ = [
    # Bases
    "auth_base",
    "study_base",
    "finance_base",
    "integration_base",
    # Auth
    "User",
    # Study
    "Group",
    "Subject",
    "Schedule",
    "UserSubject",
    # Finance
    "Debt",
    "Dop",
    # Integration
    "IntegrationLog",
    "IntegrationToken",
]
