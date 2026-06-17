import enum
from datetime import date
from sqlalchemy import String, Integer, Float, Text, ForeignKey, Enum as SAEnum, Date, Table, Column
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class EventType(str, enum.Enum):
    NO_SCHOOL = "NO_SCHOOL"
    PROJECT_WEEK = "PROJECT_WEEK"
    EXCURSION = "EXCURSION"
    EXAM_WEEK = "EXAM_WEEK"
    OTHER = "OTHER"


class EventScope(str, enum.Enum):
    SCHOOL_WIDE = "SCHOOL_WIDE"
    PER_CLASS = "PER_CLASS"


special_event_classes = Table(
    "special_event_classes",
    Base.metadata,
    Column("special_event_id", Integer, ForeignKey("special_events.id", ondelete="CASCADE"), primary_key=True),
    Column("student_class_id", Integer, ForeignKey("student_classes.id", ondelete="CASCADE"), primary_key=True),
)


class SpecialEvent(Base, TimestampMixin):
    __tablename__ = "special_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[EventType] = mapped_column(SAEnum(EventType, name="eventtype"))
    scope: Mapped[EventScope] = mapped_column(SAEnum(EventScope, name="eventscope"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    # None = 0 teaching hours during this period; set if partial teaching occurs
    hours_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    school: Mapped["School"] = relationship(back_populates="special_events")
    classes: Mapped[list["StudentClass"]] = relationship(
        secondary=special_event_classes, lazy="selectin"
    )
