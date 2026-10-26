# schemas/auth_schema.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from enums.user_enums import SocialNetworkLinkType


class LoginRequest(BaseModel):
    """Схема для входа по email и паролю."""
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., min_length=6, description="Пароль")


class RegisterRequest(BaseModel):
    """Схема для регистрации нового пользователя."""
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., min_length=6, description="Пароль")
    full_name: Optional[str] = Field(None, description="Полное имя")


class SocialLoginRequest(BaseModel):
    """Схема для входа через социальную сеть."""
    link_type: SocialNetworkLinkType = Field(..., description="Тип социальной сети")
    social_id: int = Field(..., description="ID пользователя в социальной сети")
    email: Optional[EmailStr] = Field(None, description="Email (опционально)")


class TokenResponse(BaseModel):
    """Схема ответа с токенами."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Тип токена")
    user_id: int = Field(..., description="ID пользователя")
    role: str = Field(..., description="Роль пользователя")
    is_new_user: Optional[bool] = Field(None, description="True, если пользователь только что создан")