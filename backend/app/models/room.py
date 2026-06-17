import enum
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base


class RoomType(str, enum.Enum):
    STANDARD = "STANDARD"
    GYM = "GYM"
    SCIENCE_LAB = "SCIENCE_LAB"
    COMPUTER = "COMPUTER"
    MUSIC = "MUSIC"
    WORKSHOP = "WORKSHOP"
    KITCHEN = "KITCHEN"
    ART = "ART"
    OTHER = "OTHER"


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    short_code: Mapped[str] = mapped_column(String(10))
    capacity: Mapped[int] = mapped_column(Integer)
    room_type: Mapped[RoomType] = mapped_column(Enum(RoomType, name="roomtype"), default=RoomType.STANDARD)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school: Mapped["School"] = relationship(back_populates="rooms")
    unavailabilities: Mapped[list["RoomUnavailability"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    schedule_entries: Mapped[list["ScheduleEntry"]] = relationship(back_populates="room", passive_deletes=True)
