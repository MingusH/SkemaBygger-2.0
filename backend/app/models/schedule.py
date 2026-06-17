import enum
from sqlalchemy import String, Enum, ForeignKey, DateTime, Float, JSON, Boolean, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime
from .base import Base, TimestampMixin


class ScheduleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    PUBLISHED = "PUBLISHED"


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    academic_year: Mapped[str] = mapped_column(String(9))
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, name="schedulestatus"), default=ScheduleStatus.DRAFT
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    algorithm_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    school: Mapped["School"] = relationship(back_populates="schedules")
    entries: Mapped[list["ScheduleEntry"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class ScheduleEntry(Base):
    """One placed lesson. Either a regular assignment (assignment_id) OR one
    elective-band offering (elective_offering_id) goes in time slot T in room R."""
    __tablename__ = "schedule_entries"
    __table_args__ = (
        UniqueConstraint("schedule_id", "time_slot_id", "room_id"),
        CheckConstraint(
            "(assignment_id IS NULL) <> (elective_offering_id IS NULL)",
            name="ck_entry_assignment_xor_offering",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), nullable=True)
    elective_offering_id: Mapped[int | None] = mapped_column(ForeignKey("elective_offerings.id", ondelete="CASCADE"), nullable=True)
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id", ondelete="CASCADE"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    schedule: Mapped["Schedule"] = relationship(back_populates="entries")
    assignment: Mapped["Assignment | None"] = relationship(back_populates="schedule_entries")
    elective_offering: Mapped["ElectiveOffering | None"] = relationship()
    time_slot: Mapped["TimeSlot"] = relationship(back_populates="schedule_entries")
    room: Mapped["Room"] = relationship(back_populates="schedule_entries")
