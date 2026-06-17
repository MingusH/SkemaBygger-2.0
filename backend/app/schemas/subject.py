from pydantic import BaseModel, ConfigDict
from app.models.subject import SubjectCategory
from app.models.room import RoomType


class MinistryHoursRead(BaseModel):
    grade: int
    hours_per_week: float
    model_config = ConfigDict(from_attributes=True)


class ElectiveSlotMetaRead(BaseModel):
    slot_key: str
    has_exam: bool
    model_config = ConfigDict(from_attributes=True)


class SubjectCreate(BaseModel):
    """Create a custom (non-UVM) subject, e.g. "Klassens tid". Such subjects have no
    ministry_hours, so they stay out of the UVM auto-fill and the grade-total targets;
    you assign them manually per class."""
    name: str
    short_code: str
    category: SubjectCategory = SubjectCategory.HUMANISTISK
    color_hex: str | None = None
    required_room_type: RoomType | None = None
    double_lessons: bool = False
    priority: int = 200  # high number = low priority; won't claim surplus timebank hours


class SubjectUpdate(BaseModel):
    requires_special_room: bool | None = None
    required_room_type: RoomType | None = None
    color_hex: str | None = None
    double_lessons: bool | None = None
    priority: int | None = None
    add_extra: bool | None = None


class SubjectRead(BaseModel):
    id: int
    school_id: int
    name: str
    short_code: str
    category: SubjectCategory
    color_hex: str | None
    requires_special_room: bool
    required_room_type: RoomType | None = None
    double_lessons: bool = False
    is_elective_slot: bool
    priority: int = 100
    add_extra: bool = True
    ministry_hours: list[MinistryHoursRead] = []
    elective_meta: ElectiveSlotMetaRead | None = None
    model_config = ConfigDict(from_attributes=True)
