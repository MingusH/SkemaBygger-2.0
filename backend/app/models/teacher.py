from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    short_code: Mapped[str] = mapped_column(String(10))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_hours_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    school: Mapped["School"] = relationship(back_populates="teachers")
    teacher_subjects: Mapped[list["TeacherSubject"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    unavailabilities: Mapped[list["TeacherUnavailability"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="teacher", cascade="all, delete-orphan", passive_deletes=True)


class TeacherSubject(Base):
    """Qualification: teacher is allowed to teach this subject."""
    __tablename__ = "teacher_subjects"
    __table_args__ = (UniqueConstraint("teacher_id", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))

    teacher: Mapped["Teacher"] = relationship(back_populates="teacher_subjects")
    subject: Mapped["Subject"] = relationship(back_populates="teacher_subjects")
