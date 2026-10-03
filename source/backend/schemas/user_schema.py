from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Базовые схемы ----------

class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    group_id: Optional[int] = None


class UserCreate(UserBase):
    """Схема для создания пользователя."""
    pass


class UserUpdate(BaseModel):
    """Схема для частичного обновления (все поля опциональны)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    group_id: Optional[int] = None


class UserUpdatePartial(UserUpdate):
    """Синоним для PATCH (оставлен для совместимости)."""
    pass


# ---------- Схемы вывода ----------

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UserReadWithRelations(UserRead):
    """Схема с вложенными связями (использовать с selectinload/joinedload)."""

    model_config = ConfigDict(from_attributes=True)

    # Импорты лучше делать локально, чтобы избежать циклических зависимостей
    # group: Optional["GroupRead"] = None
    # debts: list["DebtRead"] = []
    # user_subjects: list["UserSubjectRead"] = []
    # dops: list["DopRead"] = []