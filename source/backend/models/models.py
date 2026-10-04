from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Связи (Relations)
    users: Mapped[List["User"]] = relationship(back_populates="group")
    schedules: Mapped[List["Schedule"]] = relationship(back_populates="group")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    telegram_id: Mapped[int] = mapped_column(String)
    VK_id: Mapped[int] = mapped_column(String)
    MAX_id: Mapped[int] = mapped_column(Integer)

    # Связи
    group: Mapped[Optional["Group"]] = relationship(back_populates="users")
    debts: Mapped[List["Debt"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_subjects: Mapped[List["UserSubject"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    dops: Mapped[List["Dop"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Связи
    schedules: Mapped[List["Schedule"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    debts: Mapped[List["Debt"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    user_subjects: Mapped[List["UserSubject"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    classroom: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Связи
    group: Mapped["Group"] = relationship(back_populates="schedules")
    subject: Mapped["Subject"] = relationship(back_populates="schedules")


class UserSubject(Base):
    __tablename__ = "user_subjects"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True
    )

    # Связи
    user: Mapped["User"] = relationship(back_populates="user_subjects")
    subject: Mapped["Subject"] = relationship(back_populates="user_subjects")


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Связи
    user: Mapped["User"] = relationship(back_populates="debts")
    subject: Mapped["Subject"] = relationship(back_populates="debts")


class Dop(Base):
    __tablename__ = "dop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_name: Mapped[str] = mapped_column(String, nullable=False)

    # Связи
    user: Mapped["User"] = relationship(back_populates="dops")