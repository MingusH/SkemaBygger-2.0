import enum
from sqlalchemy import Integer, Float
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base


class GradeMinimumHours(Base):
    """Grade-level yearly totals from the Danish ministry PDF (grades 0-9).
    Global table — not per school. Populated by seed-subjects endpoint."""
    __tablename__ = "grade_minimum_hours"

    grade: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0-9
    annual_minimum: Mapped[float] = mapped_column(Float)   # weekly 45-min lessons equiv
    timebank_hours: Mapped[float] = mapped_column(Float)   # school's flex pool
    total_annual: Mapped[float] = mapped_column(Float)     # annual_minimum + timebank_hours
