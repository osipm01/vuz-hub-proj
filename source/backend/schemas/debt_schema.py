# schemas/debt_schema.py
from pydantic import BaseModel


class DebtCreate(BaseModel):
    user_id: int
    subject_id: int
    description: str

class DebtUpdate(BaseModel):
    subject_id: int | None = None
    description: str | None = None
    is_resolved: bool | None = None