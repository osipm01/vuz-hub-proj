# schemas/subject_schema.py
from pydantic import BaseModel


class SubjectCreate(BaseModel):
    name: str

class SubjectUpdate(BaseModel):
    name: str | None = None