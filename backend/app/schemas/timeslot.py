from datetime import time
from pydantic import BaseModel, ConfigDict


class TimeSlotBase(BaseModel):
    day_of_week: int   # 1=Monday .. 5=Friday
    period_number: int
    start_time: time
    end_time: time
    label: str | None = None


class TimeSlotCreate(TimeSlotBase):
    pass


class TimeSlotUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    label: str | None = None


class TimeSlotRead(TimeSlotBase):
    id: int
    school_id: int
    model_config = ConfigDict(from_attributes=True)
