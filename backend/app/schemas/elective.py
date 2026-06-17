from pydantic import BaseModel, ConfigDict
from app.models.elective import ElectiveBandType


class ElectiveOfferingCreate(BaseModel):
    subject_id: int
    teacher_id: int
    room_id: int


class ElectiveOfferingRead(ElectiveOfferingCreate):
    id: int
    band_id: int
    model_config = ConfigDict(from_attributes=True)


class ElectiveBandCreate(BaseModel):
    grade_level: int
    band_type: ElectiveBandType
    name: str
    hours_per_week: int
    requires_consecutive: bool = True
    draws_timebank: bool = False
    offerings: list[ElectiveOfferingCreate] = []


class ElectiveBandUpdate(BaseModel):
    grade_level: int | None = None
    band_type: ElectiveBandType | None = None
    name: str | None = None
    hours_per_week: int | None = None
    requires_consecutive: bool | None = None
    draws_timebank: bool | None = None


class ElectiveBandRead(BaseModel):
    id: int
    school_id: int
    grade_level: int
    band_type: ElectiveBandType
    name: str
    hours_per_week: int
    requires_consecutive: bool
    draws_timebank: bool
    academic_year: str
    offerings: list[ElectiveOfferingRead] = []
    model_config = ConfigDict(from_attributes=True)
