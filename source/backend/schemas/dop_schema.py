# schemas/dop_schema.py
from pydantic import BaseModel


class DopCreate(BaseModel):
    user_id: int
    organization_name: str

class DopUpdate(BaseModel):
    organization_name: str | None = None