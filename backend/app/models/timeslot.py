from sqlalchemy import Integer, ForeignKey, Time, String, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import time
from .base import Base


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (UniqueConstraint("school_id", "day_of_week", "period_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(Integer)   # 1=Monday .. 5=Friday
    period_number: Mapped[int] = mapped_column(Integer) # 1-based
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    school: Mapped["School"] = relationship(back_populates="time_slots")
    teacher_unavailabilities: Mapped[list["TeacherUnavailability"]] = relationship(back_populates="time_slot")
    room_unavailabilities: Mapped[list["RoomUnavailability"]] = relationship(back_populates="time_slot")
    class_unavailabilities: Mapped[list["ClassUnavailability"]] = relationship(back_populates="time_slot")
    schedule_entries: Mapped[list["ScheduleEntry"]] = relationship(back_populates="time_slot")
