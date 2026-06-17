from pydantic import BaseModel, ConfigDict


class AssignmentBase(BaseModel):
    teacher_id: int
    subject_id: int
    student_class_id: int
    hours_per_week: int
    preferred_room_id: int | None = None
    requires_consecutive: bool = False
    min_days_between_lessons: int | None = None
    parallel_group_id: int | None = None
    academic_year: str


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    hours_per_week: int | None = None
    preferred_room_id: int | None = None
    requires_consecutive: bool | None = None
    min_days_between_lessons: int | None = None
    parallel_group_id: int | None = None


class AssignmentRead(AssignmentBase):
    id: int
    school_id: int
    model_config = ConfigDict(from_attributes=True)
