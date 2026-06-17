from sqlalchemy import Integer, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base


class Assignment(Base):
    """
    Core scheduling input: teacher T teaches subject S to class C for H hours/week.

    parallel_group_id: assignments sharing this value must be placed at the same
    time slot by the solver (used for Tysk/Fransk split-class scenarios).
    """
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", "student_class_id", "academic_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    student_class_id: Mapped[int] = mapped_column(ForeignKey("student_classes.id", ondelete="CASCADE"))
    preferred_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    requires_consecutive: Mapped[bool] = mapped_column(Boolean, default=False)
    min_days_between_lessons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parallel_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academic_year: Mapped[str] = mapped_column(String(9))

    school: Mapped["School"] = relationship(back_populates="assignments")
    teacher: Mapped["Teacher"] = relationship(back_populates="assignments")
    subject: Mapped["Subject"] = relationship(back_populates="assignments")
    student_class: Mapped["StudentClass"] = relationship(back_populates="assignments")
    preferred_room: Mapped["Room | None"] = relationship(foreign_keys=[preferred_room_id])
    schedule_entries: Mapped[list["ScheduleEntry"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
