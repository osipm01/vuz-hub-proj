# schemas/debt_schema.py
from pydantic import BaseModel, ConfigDict


class DebtCreate(BaseModel):
    user_id: int
    subject_id: int
    description: str

class DebtUpdate(BaseModel):
    subject_id: int | None = None
    description: str | None = None
    is_resolved: bool | None = None

class DebtRead(DebtCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int