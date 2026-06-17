"""add special_events, grade_minimum_hours, weeks_per_year

Revision ID: 005
Revises: 004
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # weeks_per_year on schools (IF NOT EXISTS for idempotency after partial run)
    op.execute("ALTER TABLE schools ADD COLUMN IF NOT EXISTS weeks_per_year INTEGER NOT NULL DEFAULT 40")

    # Global grade-level ministry totals
    op.execute("DROP TABLE IF EXISTS grade_minimum_hours")
    op.execute("""
        CREATE TABLE grade_minimum_hours (
            grade INTEGER PRIMARY KEY,
            annual_minimum DOUBLE PRECISION NOT NULL,
            timebank_hours DOUBLE PRECISION NOT NULL,
            total_annual DOUBLE PRECISION NOT NULL
        )
    """)

    # Postgres doesn't support CREATE TYPE IF NOT EXISTS — use DO block
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventtype AS ENUM ('NO_SCHOOL', 'PROJECT_WEEK', 'EXCURSION', 'EXAM_WEEK', 'OTHER');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventscope AS ENUM ('SCHOOL_WIDE', 'PER_CLASS');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Drop any leftovers from a partial previous run
    op.execute("DROP TABLE IF EXISTS special_event_classes")
    op.execute("DROP TABLE IF EXISTS special_events")

    op.execute("""
        CREATE TABLE special_events (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            event_type eventtype NOT NULL,
            scope eventscope NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            hours_override DOUBLE PRECISION,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE special_event_classes (
            special_event_id INTEGER NOT NULL REFERENCES special_events(id) ON DELETE CASCADE,
            student_class_id INTEGER NOT NULL REFERENCES student_classes(id) ON DELETE CASCADE,
            PRIMARY KEY (special_event_id, student_class_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS special_event_classes")
    op.execute("DROP TABLE IF EXISTS special_events")
    op.execute("DROP TABLE IF EXISTS grade_minimum_hours")
    op.execute("ALTER TABLE schools DROP COLUMN IF EXISTS weeks_per_year")
    op.execute("DROP TYPE IF EXISTS eventscope")
    op.execute("DROP TYPE IF EXISTS eventtype")
