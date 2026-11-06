from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from enums.user_enums import UserRole


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # group_id не имеет ForeignKey — таблица groups в study-service
    group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    role: Mapped[UserRole] = mapped_column(String, nullable=False, default=UserRole.USER)

    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    VK_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    MAX_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
