from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from enums.user_enums import SocialNetworkLinkType


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
    """Синоним для PATCH."""
    pass


# ============================================================
# ВЫВОД
# ============================================================

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UserReadWithRelations(UserRead):
    """Схема с вложенными связями (использовать с selectinload/joinedload)."""
    model_config = ConfigDict(from_attributes=True)

    # group: Optional["GroupRead"] = None
    # debts: list["DebtRead"] = []
    # user_subjects: list["UserSubjectRead"] = []
    # dops: list["DopRead"] = []


# ============================================================
# СОЦСЕТИ: инфо о привязках
# ============================================================

class SocialLinkInfo(BaseModel):
    """Одна привязанная соцсеть."""
    link_type: SocialNetworkLinkType
    social_id: Optional[Union[int, str]] = None


class SocialLinksResponse(BaseModel):
    """Ответ со списком привязанных соцсетей пользователя."""
    user_id: int
    links: list[SocialLinkInfo] = Field(default_factory=list)


def build_social_links(user) -> SocialLinksResponse:
    """Собирает SocialLinksResponse из ORM-объекта User."""
    links: list[SocialLinkInfo] = []
    if getattr(user, "VK_id", None) is not None:
        links.append(SocialLinkInfo(link_type=SocialNetworkLinkType.VK, social_id=user.VK_id))
    if getattr(user, "MAX_id", None) is not None:
        links.append(SocialLinkInfo(link_type=SocialNetworkLinkType.MAX_id, social_id=user.MAX_id))
    if getattr(user, "telegram_id", None) is not None:
        links.append(SocialLinkInfo(link_type=SocialNetworkLinkType.TG_ID, social_id=user.telegram_id))
    return SocialLinksResponse(user_id=user.id, links=links)


# ============================================================
# СОЦСЕТИ: привязка / отвязка
# ============================================================

class SocialLinkRequest(BaseModel):
    """POST /users/me/social/link — привязать соцсеть к текущему юзеру."""
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["tg_id"])
    social_id: Union[int, str] = Field(..., examples=[123456789])

    @field_validator("social_id")
    @classmethod
    def coerce_social_id(cls, v):
        if isinstance(v, str) and v.isdigit():
            return int(v)
        if isinstance(v, int) and v <= 0:
            raise ValueError("social_id должен быть положительным")
        return v


class SocialUnlinkRequest(BaseModel):
    """POST /users/me/social/unlink — отвязать соцсеть."""
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["vk"])


# ============================================================
# АВТОРИЗАЦИЯ ЧЕРЕЗ СОЦСЕТЬ
# ============================================================

class SocialAuthRequest(BaseModel):
    """Запрос на вход/регистрацию через соцсеть.

    Если пользователя с таким (link_type, social_id) нет —
    можно создать нового (при наличии email/name).
    """
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["tg_id"])
    social_id: Union[int, str] = Field(..., examples=[123456789])

    # Данные для автосоздания (опциональны — нужны только при регистрации)
    email: Optional[EmailStr] = Field(None, examples=["user@example.com"])
    name: Optional[str] = Field(None, min_length=1, max_length=255)

    @field_validator("social_id")
    @classmethod
    def coerce_social_id(cls, v):
        if isinstance(v, str) and v.isdigit():
            return int(v)
        if isinstance(v, int) and v <= 0:
            raise ValueError("social_id должен быть положительным")
        return v


class SocialAuthResponse(BaseModel):
    """Ответ после успешной авторизации через соцсеть."""
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    link_type: SocialNetworkLinkType
    social_id: Union[int, str]
    is_new_user: bool = False

    # Опционально: токен, если у тебя JWT
    # access_token: Optional[str] = None
    # token_type: str = "bearer"


# ============================================================
# PATCH сразу нескольких привязок
# ============================================================

class SocialLinksPatch(BaseModel):
    """PATCH — обновить одну или несколько привязок сразу.

    Пример: {"vk": 123, "tg_id": null, "max_id": 456}
    """
    model_config = ConfigDict(extra="forbid")

    vk: Optional[int] = None
    max_id: Optional[int] = None
    tg_id: Optional[int] = None

    def to_link_map(self) -> dict[SocialNetworkLinkType, Optional[int]]:
        mapping = {
            SocialNetworkLinkType.VK: self.vk,
            SocialNetworkLinkType.MAX_id: self.max_id,
            SocialNetworkLinkType.TG_ID: self.tg_id,
        }
        return {k: v for k, v in mapping.items() if k in self.model_fields_set}


class SocialLinksPatchResult(BaseModel):
    user_id: int
    updated: list[SocialNetworkLinkType] = Field(default_factory=list)
    skipped: list[SocialNetworkLinkType] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)