"""add subjects.add_extra (eligible for surplus/extra lessons)

Revision ID: 010
Revises: 009
Create Date: 2026-06-17
"""
from typing import Sequence, Union
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subjects ADD COLUMN IF NOT EXISTS add_extra BOOLEAN NOT NULL DEFAULT true")


def downgrade() -> None:
    op.execute("ALTER TABLE subjects DROP COLUMN IF EXISTS add_extra")
