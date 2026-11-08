from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from enums.user_enums import SocialNetworkLinkType, UserRole


# ============================================================
# БАЗОВЫЕ
# ============================================================
class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    group_id: Optional[int] = None

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: Optional[str] = None
    role: Optional[str] = None
    group_id: Optional[int] = None
    telegram_id: Optional[int] = None
    VK_id: Optional[int] = None
    MAX_id: Optional[int] = None


class UserUpdate(BaseModel):
    """Частичное обновление профиля. Роль здесь НЕ меняется."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    group_id: Optional[int] = None


class UserRoleUpdate(BaseModel):
    """Отдельный админский payload для смены роли."""
    model_config = ConfigDict(extra="forbid")

    role: UserRole


# ============================================================
# ВЫВОД
# ============================================================
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    group_id: Optional[int] = None
    role: UserRole
    created_at: datetime


# ============================================================
# СОЦСЕТИ: инфо о привязках
# ============================================================
class SocialLinkInfo(BaseModel):
    link_type: SocialNetworkLinkType
    social_id: Optional[int] = None


class SocialLinksResponse(BaseModel):
    user_id: int
    links: list[SocialLinkInfo] = Field(default_factory=list)


def build_social_links(user) -> SocialLinksResponse:  # noqa: ANN001 — ORM User
    """Собирает SocialLinksResponse из ORM-объекта User."""
    links: list[SocialLinkInfo] = []
    if getattr(user, "VK_id", None) is not None:
        links.append(
            SocialLinkInfo(link_type=SocialNetworkLinkType.VK, social_id=user.VK_id)
        )
    if getattr(user, "MAX_id", None) is not None:
        links.append(
            SocialLinkInfo(link_type=SocialNetworkLinkType.MAX_id, social_id=user.MAX_id)
        )
    if getattr(user, "telegram_id", None) is not None:
        links.append(
            SocialLinkInfo(
                link_type=SocialNetworkLinkType.TG_ID, social_id=user.telegram_id
            )
        )
    return SocialLinksResponse(user_id=user.id, links=links)


# ============================================================
# СОЦСЕТИ: привязка / отвязка
# ============================================================
class SocialLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["tg_id"])
    social_id: int = Field(..., gt=0, examples=[123456789])


class SocialUnlinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["vk"])


# ============================================================
# АВТОРИЗАЦИЯ ЧЕРЕЗ СОЦСЕТЬ
# ============================================================
class SocialAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_type: SocialNetworkLinkType = Field(..., examples=["tg_id"])
    social_id: int = Field(..., gt=0, examples=[123456789])

    email: Optional[EmailStr] = Field(None, examples=["user@example.com"])
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class SocialAuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    link_type: SocialNetworkLinkType
    social_id: int
    is_new_user: bool = False


# ============================================================
# PATCH сразу нескольких привязок
# ============================================================
class SocialLinksPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vk: Optional[int] = Field(None, gt=0)
    max_id: Optional[int] = Field(None, gt=0)
    tg_id: Optional[int] = Field(None, gt=0)

    def to_link_map(self) -> dict[SocialNetworkLinkType, Optional[int]]:
        mapping: dict[SocialNetworkLinkType, Optional[int]] = {
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