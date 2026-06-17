from pydantic import BaseModel, ConfigDict


class TeacherBase(BaseModel):
    first_name: str
    last_name: str
    short_code: str
    email: str | None = None
    max_hours_per_week: int | None = None


class TeacherCreate(TeacherBase):
    subject_ids: list[int] = []


class TeacherUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    short_code: str | None = None
    email: str | None = None
    max_hours_per_week: int | None = None
    is_active: bool | None = None
    subject_ids: list[int] | None = None  # when given, replaces the teacher's qualifications


class TeacherRead(TeacherBase):
    id: int
    school_id: int
    is_active: bool
    subject_ids: list[int] = []
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_subjects(cls, teacher):
        data = cls.model_validate(teacher)
        data.subject_ids = [ts.subject_id for ts in teacher.teacher_subjects]
        return data


class TeacherSubjectCreate(BaseModel):
    subject_id: int
