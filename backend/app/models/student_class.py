from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base


class StudentClass(Base):
    __tablename__ = "student_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(20))          # e.g. "7B"
    grade_level: Mapped[int] = mapped_column(Integer)      # 1-9
    student_count: Mapped[int] = mapped_column(Integer)
    home_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    school: Mapped["School"] = relationship(back_populates="student_classes")
    home_room: Mapped["Room | None"] = relationship(foreign_keys=[home_room_id])
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="student_class", cascade="all, delete-orphan", passive_deletes=True)
    unavailabilities: Mapped[list["ClassUnavailability"]] = relationship(back_populates="student_class", cascade="all, delete-orphan")
