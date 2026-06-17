import enum
from sqlalchemy import String, Integer, Enum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base


class ConstraintType(str, enum.Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class EntityType(str, enum.Enum):
    TEACHER = "TEACHER"
    CLASS = "CLASS"
    SUBJECT = "SUBJECT"
    ROOM = "ROOM"


class PreferenceType(str, enum.Enum):
    PREFER_MORNING = "PREFER_MORNING"
    AVOID_LAST_PERIOD = "AVOID_LAST_PERIOD"
    NO_ISOLATED_LESSONS = "NO_ISOLATED_LESSONS"
    MAX_DAILY_HOURS = "MAX_DAILY_HOURS"
    SUBJECT_SPREAD = "SUBJECT_SPREAD"


class TeacherUnavailability(Base):
    __tablename__ = "teacher_unavailabilities"
    __table_args__ = (UniqueConstraint("teacher_id", "time_slot_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id", ondelete="CASCADE"))
    constraint_type: Mapped[ConstraintType] = mapped_column(
        Enum(ConstraintType, name="constrainttype"), default=ConstraintType.HARD
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    teacher: Mapped["Teacher"] = relationship(back_populates="unavailabilities")
    time_slot: Mapped["TimeSlot"] = relationship(back_populates="teacher_unavailabilities")


class RoomUnavailability(Base):
    __tablename__ = "room_unavailabilities"
    __table_args__ = (UniqueConstraint("room_id", "time_slot_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id", ondelete="CASCADE"))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    room: Mapped["Room"] = relationship(back_populates="unavailabilities")
    time_slot: Mapped["TimeSlot"] = relationship(back_populates="room_unavailabilities")


class ClassUnavailability(Base):
    __tablename__ = "class_unavailabilities"
    __table_args__ = (UniqueConstraint("student_class_id", "time_slot_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_class_id: Mapped[int] = mapped_column(ForeignKey("student_classes.id", ondelete="CASCADE"))
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id", ondelete="CASCADE"))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    student_class: Mapped["StudentClass"] = relationship(back_populates="unavailabilities")
    time_slot: Mapped["TimeSlot"] = relationship(back_populates="class_unavailabilities")


class SchedulingPreference(Base):
    """Soft wishes that the solver tries to honor, weighted 1-10."""
    __tablename__ = "scheduling_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType, name="entitytype"))
    entity_id: Mapped[int] = mapped_column(Integer)
    preference_type: Mapped[PreferenceType] = mapped_column(Enum(PreferenceType, name="preferencetype"))
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=5)

    school: Mapped["School"] = relationship(back_populates="scheduling_preferences")
