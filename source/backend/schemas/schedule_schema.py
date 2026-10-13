# schemas/schedule_schema.py
from datetime import datetime

from pydantic import BaseModel


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