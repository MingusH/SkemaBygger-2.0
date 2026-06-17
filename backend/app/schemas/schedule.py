from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.schedule import ScheduleStatus


class ScheduleCreate(BaseModel):
    name: str
    academic_year: str
    algorithm_params: dict | None = None


class ScheduleRead(BaseModel):
    id: int
    school_id: int
    name: str
    academic_year: str
    status: ScheduleStatus
    generated_at: datetime | None
    score: float | None
    model_config = ConfigDict(from_attributes=True)


class ScheduleEntryRead(BaseModel):
    id: int
    schedule_id: int
    assignment_id: int | None
    elective_offering_id: int | None
    time_slot_id: int
    room_id: int
    is_locked: bool
    model_config = ConfigDict(from_attributes=True)
