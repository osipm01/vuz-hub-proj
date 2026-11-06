# schemas/user_subject_schema.py
from pydantic import BaseModel, ConfigDict


class UserSubjectCreate(BaseModel):
    user_id: int
    subject_id: int

class UserSubjectRead(UserSubjectCreate):
    model_config = ConfigDict(from_attributes=True)