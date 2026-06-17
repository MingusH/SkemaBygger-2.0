from pydantic import BaseModel, ConfigDict
from app.models.room import RoomType


class RoomBase(BaseModel):
    name: str
    short_code: str
    capacity: int
    room_type: RoomType = RoomType.STANDARD


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = None
    short_code: str | None = None
    capacity: int | None = None
    room_type: RoomType | None = None
    is_active: bool | None = None


class RoomRead(RoomBase):
    id: int
    school_id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
