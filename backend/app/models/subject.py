import enum
from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer, Float, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base
from .room import RoomType


class SubjectCategory(str, enum.Enum):
    HUMANISTISK = "humanistisk"
    NATURFAG = "naturfag"
    PRAKTISK_MUSISK = "praktisk_musisk"
    VALGFAG = "valgfag"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    short_code: Mapped[str] = mapped_column(String(10))
    category: Mapped[SubjectCategory] = mapped_column(
        Enum(SubjectCategory, name="subjectcategory", values_callable=lambda obj: [e.value for e in obj])
    )
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    requires_special_room: Mapped[bool] = mapped_column(Boolean, default=False)
    # Which room type this subject must be taught in (e.g. Idræt -> GYM). When set,
    # the solver treats it as a hard constraint. None = no specific type required.
    required_room_type: Mapped[RoomType | None] = mapped_column(
        Enum(RoomType, name="roomtype", create_type=False), nullable=True
    )
    # When True, the solver schedules this subject as back-to-back double lessons
    # (e.g. Idræt, Billedkunst). A subject-level property so it survives assignment
    # recreation and applies to every school that seeds this subject.
    double_lessons: Mapped[bool] = mapped_column(Boolean, default=False)
    is_elective_slot: Mapped[bool] = mapped_column(Boolean, default=False)
    # When False, the subject only ever gets its ministry minimum — it is excluded from
    # the surplus ("extra") lessons distributed to fill the grade total. Turn this off for
    # subjects that must not be padded (e.g. Idræt, where an odd extra lesson would leave a
    # lone single period instead of a clean double).
    add_extra: Mapped[bool] = mapped_column(Boolean, default=True)
    # Lower = higher priority. Controls which subjects receive the surplus hours
    # above the ministry minimum when auto-assigning toward the grade total.
    priority: Mapped[int] = mapped_column(Integer, default=100)

    school: Mapped["School"] = relationship(back_populates="subjects")
    elective_meta: Mapped["ElectiveSlotMeta | None"] = relationship(back_populates="subject", uselist=False, cascade="all, delete-orphan")
    ministry_hours: Mapped[list["MinistryHours"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    teacher_subjects: Mapped[list["TeacherSubject"]] = relationship(back_populates="subject")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="subject", cascade="all, delete-orphan", passive_deletes=True)


class ElectiveSlotMeta(Base):
    __tablename__ = "elective_slot_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), unique=True)
    slot_key: Mapped[str] = mapped_column(String(50))  # e.g. "pm_valgfag_1"
    has_exam: Mapped[bool] = mapped_column(Boolean, default=False)

    subject: Mapped["Subject"] = relationship(back_populates="elective_meta")


class MinistryHours(Base):
    """Ministry-mandated weekly lessons per subject per grade (1-9)."""
    __tablename__ = "ministry_hours"
    __table_args__ = (UniqueConstraint("subject_id", "grade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    grade: Mapped[int] = mapped_column(Integer)          # 1-9
    hours_per_week: Mapped[float] = mapped_column(Float) # weekly 45-min lessons

    subject: Mapped["Subject"] = relationship(back_populates="ministry_hours")
