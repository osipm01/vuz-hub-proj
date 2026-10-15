# schemas/subject_schema.py
from pydantic import BaseModel, ConfigDict


class SubjectCreate(BaseModel):
    name: str

class SubjectUpdate(BaseModel):
    name: str | None = None

class SubjectRead(SubjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int