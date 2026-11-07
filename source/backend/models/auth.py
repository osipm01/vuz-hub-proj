from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from enums.user_enums import UserRole
from models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    role: Mapped[UserRole] = mapped_column(String, nullable=False, default=UserRole.USER)

    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    VK_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    MAX_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)

    # Note: relationships to Debt, Dop, UserSubject, Group are intentionally NOT defined here.
    # Cross-service relationships break SQLAlchemy mapper inspection when models are imported
    # from different databases. Use explicit queries in services if needed.
