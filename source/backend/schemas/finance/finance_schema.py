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


class DopCreate(BaseModel):
    user_id: int
    organization_name: str


class DopUpdate(BaseModel):
    organization_name: str | None = None


class DopRead(DopCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
