# schemas/user_subject_schema.py
from pydantic import BaseModel


class UserSubjectCreate(BaseModel):
    user_id: int
    subject_id: int