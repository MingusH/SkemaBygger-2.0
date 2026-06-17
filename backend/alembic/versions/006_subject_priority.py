"""add subjects.priority and backfill a ranking

Revision ID: 006
Revises: 005
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subjects ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100")
    # Seed a sensible initial ranking: within each school, non-elective subjects
    # ordered by total ministry hours (desc) get priority 1, 2, 3, ...
    op.execute("""
        UPDATE subjects s SET priority = sub.rank FROM (
            SELECT s2.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY s2.school_id
                       ORDER BY COALESCE(SUM(mh.hours_per_week), 0) DESC, s2.name
                   ) AS rank
            FROM subjects s2
            LEFT JOIN ministry_hours mh ON mh.subject_id = s2.id
            WHERE s2.is_elective_slot = false
            GROUP BY s2.id, s2.school_id, s2.name
        ) sub
        WHERE s.id = sub.id
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE subjects DROP COLUMN IF EXISTS priority")
