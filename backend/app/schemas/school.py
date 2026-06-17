from pydantic import BaseModel, ConfigDict


class SchoolBase(BaseModel):
    name: str
    short_name: str
    academic_year: str
    periods_per_day: int
    days_per_week: int = 5
    weeks_per_year: int = 40


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    academic_year: str | None = None
    periods_per_day: int | None = None
    days_per_week: int | None = None
    weeks_per_year: int | None = None


class SchoolRead(SchoolBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
