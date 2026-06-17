"""add double_lessons to subjects

Revision ID: 003
Revises: 002
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column("double_lessons", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill the subjects that are always taught as double lessons. Matches the
    # canonical names and common ministry variants (e.g. "Natur/teknologi (1.-6.)").
    op.execute(
        """
        UPDATE subjects SET double_lessons = true
        WHERE lower(name) LIKE 'idræt%'
           OR lower(name) LIKE 'natur/teknologi%'
           OR lower(name) LIKE 'madkundskab%'
           OR lower(name) LIKE 'håndværk og design%'
           OR lower(name) LIKE 'billedkunst%'
        """
    )


def downgrade() -> None:
    op.drop_column("subjects", "double_lessons")
