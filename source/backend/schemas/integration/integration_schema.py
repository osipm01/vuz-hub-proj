from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IntegrationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    is_active: bool = True


class IntegrationCreate(IntegrationBase):
    owner_id: Optional[int] = Field(None, ge=1)


class IntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    is_active: Optional[bool] = None


class IntegrationRead(IntegrationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class IntegrationTokenRead(BaseModel):
    integration_id: int
    token: str
    token_type: str = Field(..., description="bearer | api_key")
