from pydantic import BaseModel, ConfigDict


class StudentClassBase(BaseModel):
    name: str
    grade_level: int
    student_count: int
    home_room_id: int | None = None


class StudentClassCreate(StudentClassBase):
    pass


class StudentClassUpdate(BaseModel):
    name: str | None = None
    grade_level: int | None = None
    student_count: int | None = None
    home_room_id: int | None = None
    is_active: bool | None = None


class BulkClassCreate(BaseModel):
    grade_start: int
    grade_end: int
    suffixes: list[str]
    student_count: int


class StudentClassRead(StudentClassBase):
    id: int
    school_id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
