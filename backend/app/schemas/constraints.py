from pydantic import BaseModel, ConfigDict
from app.models.constraints import ConstraintType, EntityType, PreferenceType


class TeacherUnavailabilityCreate(BaseModel):
    time_slot_id: int
    constraint_type: ConstraintType = ConstraintType.HARD
    reason: str | None = None


class TeacherUnavailabilityRead(TeacherUnavailabilityCreate):
    id: int
    teacher_id: int
    model_config = ConfigDict(from_attributes=True)


class RoomUnavailabilityCreate(BaseModel):
    time_slot_id: int
    reason: str | None = None


class RoomUnavailabilityRead(RoomUnavailabilityCreate):
    id: int
    room_id: int
    model_config = ConfigDict(from_attributes=True)


class ClassUnavailabilityCreate(BaseModel):
    time_slot_id: int
    reason: str | None = None


class ClassUnavailabilityRead(ClassUnavailabilityCreate):
    id: int
    student_class_id: int
    model_config = ConfigDict(from_attributes=True)


class SchedulingPreferenceCreate(BaseModel):
    entity_type: EntityType
    entity_id: int
    preference_type: PreferenceType
    value: dict | None = None
    weight: int = 5


class SchedulingPreferenceRead(SchedulingPreferenceCreate):
    id: int
    school_id: int
    model_config = ConfigDict(from_attributes=True)
