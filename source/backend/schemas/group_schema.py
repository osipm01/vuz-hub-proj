# schemas/group_schema.py
from pydantic import BaseModel, ConfigDict

class GroupCreate(BaseModel):
    name: str

class GroupUpdate(BaseModel):
    name: str | None = None

class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class GroupReading(GroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int