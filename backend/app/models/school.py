from sqlalchemy import String, Integer
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(20))
    academic_year: Mapped[str] = mapped_column(String(9))  # "2025/2026"
    periods_per_day: Mapped[int] = mapped_column(Integer)
    days_per_week: Mapped[int] = mapped_column(Integer, default=5)
    weeks_per_year: Mapped[int] = mapped_column(Integer, default=40)

    members: Mapped[list["SchoolMember"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    time_slots: Mapped[list["TimeSlot"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    rooms: Mapped[list["Room"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    teachers: Mapped[list["Teacher"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    student_classes: Mapped[list["StudentClass"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    scheduling_preferences: Mapped[list["SchedulingPreference"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    special_events: Mapped[list["SpecialEvent"]] = relationship(back_populates="school", cascade="all, delete-orphan")
