"""Модели PostgreSQL для всех сервисов VuzHub."""

from .auth import base as auth_base
from .auth import User
from .study import base as study_base
from .study import Group, Subject, Schedule, UserSubject
from .finance import base as finance_base
from .finance import Debt, Dop
from .integration import base as integration_base
from .integration import IntegrationLog, IntegrationToken

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
