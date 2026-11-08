"""SQLAlchemy Base для всех моделей.

Все модели наследуются от единого Base из models.base.
Это обеспечивает общий реестр метаданных, необходимый
для корректной работы внешних ключей между таблицами.
"""

from models.base import Base
from models.auth import User
from models.study import Group, Subject, Schedule, UserSubject
from models.finance import Debt, Dop
from models.integration import IntegrationLog, IntegrationToken

__all__ = [
    "Base",
    "User", "Group", "Subject", "Schedule", "UserSubject",
    "Debt", "Dop",
    "IntegrationLog", "IntegrationToken",
]
