from datetime import date
from pydantic import BaseModel, ConfigDict
from app.models.special_event import EventType, EventScope


class SpecialEventCreate(BaseModel):
    name: str
    event_type: EventType
    scope: EventScope
    start_date: date
    end_date: date
    hours_override: float | None = None
    description: str | None = None
    class_ids: list[int] = []  # ignored when scope=SCHOOL_WIDE


class SpecialEventUpdate(BaseModel):
    name: str | None = None
    event_type: EventType | None = None
    scope: EventScope | None = None
    start_date: date | None = None
    end_date: date | None = None
    hours_override: float | None = None
    description: str | None = None
    class_ids: list[int] | None = None


class SpecialEventRead(BaseModel):
    id: int
    school_id: int
    name: str
    event_type: EventType
    scope: EventScope
    start_date: date
    end_date: date
    hours_override: float | None
    description: str | None
    class_ids: list[int] = []
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_classes(cls, event: object) -> "SpecialEventRead":
        d = {
            "id": event.id,
            "school_id": event.school_id,
            "name": event.name,
            "event_type": event.event_type,
            "scope": event.scope,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "hours_override": event.hours_override,
            "description": event.description,
            "class_ids": [c.id for c in event.classes],
        }
        return cls(**d)


class ClassTimeBankEntry(BaseModel):
    class_id: int
    class_name: str
    grade_level: int
    weekly_hours: float          # actual clock hours/week the class is in school (incl. breaks)
    delivered: float             # actual school clock hours/year incl. breaks, minus timebank_used
    ministry_min_hours: float    # yearly minimum requirement
    timebank_pool: float         # flex pool available above the minimum
    timebank_used: float         # clock hours drawn from the bank by events / draws-timebank bands
    balance: float               # delivered − ministry_min_hours = hours still free for events
    is_sufficient: bool


class SchoolTimeBankRead(BaseModel):
    school_id: int
    weeks_per_year: int
    schedule_id: int | None = None
    has_schedule: bool = False
    entries: list[ClassTimeBankEntry]
