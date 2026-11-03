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


class SubjectCreate(BaseModel):
    name: str


class SubjectUpdate(BaseModel):
    name: str | None = None


class SubjectRead(SubjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


from datetime import datetime  # noqa: E402


class ScheduleCreate(BaseModel):
    group_id: int
    subject_id: int
    weekday: int
    start_time: datetime
    classroom: str | None = None


class ScheduleUpdate(BaseModel):
    group_id: int | None = None
    subject_id: int | None = None
    weekday: int | None = None
    start_time: datetime | None = None
    classroom: str | None = None


class ScheduleRead(ScheduleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class UserSubjectCreate(BaseModel):
    user_id: int
    subject_id: int


class UserSubjectRead(UserSubjectCreate):
    model_config = ConfigDict(from_attributes=True)
