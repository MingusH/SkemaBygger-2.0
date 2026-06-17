import enum
from sqlalchemy import String, Integer, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class ElectiveBandType(str, enum.Enum):
    PRACTICAL = "PRACTICAL"   # praktisk/musisk valgfag
    LOCAL = "LOCAL"           # lokalt valgfag


class ElectiveBand(Base, TimestampMixin):
    """A reserved block for one grade in which several elective subjects run in
    parallel. Every active class of `grade_level` participates; the solver places
    the band into the same slot(s) for all of them."""
    __tablename__ = "elective_bands"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    grade_level: Mapped[int] = mapped_column(Integer)
    band_type: Mapped[ElectiveBandType] = mapped_column(SAEnum(ElectiveBandType, name="electivebandtype"))
    name: Mapped[str] = mapped_column(String(200))
    hours_per_week: Mapped[int] = mapped_column(Integer)          # periods the band occupies
    requires_consecutive: Mapped[bool] = mapped_column(Boolean, default=True)
    draws_timebank: Mapped[bool] = mapped_column(Boolean, default=False)  # True for the 2nd practical
    academic_year: Mapped[str] = mapped_column(String(9))

    offerings: Mapped[list["ElectiveOffering"]] = relationship(
        back_populates="band", cascade="all, delete-orphan", lazy="selectin"
    )


class ElectiveOffering(Base):
    """One subject running during a band — its own teacher and (specific) room."""
    __tablename__ = "elective_offerings"

    id: Mapped[int] = mapped_column(primary_key=True)
    band_id: Mapped[int] = mapped_column(ForeignKey("elective_bands.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))

    band: Mapped["ElectiveBand"] = relationship(back_populates="offerings")
    subject: Mapped["Subject"] = relationship()
    teacher: Mapped["Teacher"] = relationship()
    room: Mapped["Room"] = relationship()
