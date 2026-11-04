"""SQLAlchemy Base для всех сервисов.

Экспортирует base и модели для каждого сервиса.
При импорте НЕ создаёт cross-service relationships — они ломают
mapper inspection, когда модели из разных БД загружаются вместе.
"""

from .auth import Base as auth_base, User
from .study import Base as study_base, Group, Subject, Schedule, UserSubject
from .finance import Base as finance_base, Debt, Dop
from .integration import Base as integration_base, IntegrationLog, IntegrationToken

__all__ = [
    "auth_base", "study_base", "finance_base", "integration_base",
    "User", "Group", "Subject", "Schedule", "UserSubject",
    "Debt", "Dop", "IntegrationLog", "IntegrationToken",
]
