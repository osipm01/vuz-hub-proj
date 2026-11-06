# schemas/dop_schema.py
from pydantic import BaseModel, ConfigDict


class DopCreate(BaseModel):
    user_id: int
    organization_name: str

class DopUpdate(BaseModel):
    organization_name: str | None = None

class DopRead(DopCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int