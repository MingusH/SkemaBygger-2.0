"""add required_room_type to subjects

Revision ID: 002
Revises: 001
Create Date: 2026-06-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # roomtype enum already exists (created in 001) — reuse it, don't recreate.
    op.add_column(
        "subjects",
        sa.Column(
            "required_room_type",
            PgEnum(
                "STANDARD", "GYM", "SCIENCE_LAB", "COMPUTER", "MUSIC", "WORKSHOP", "KITCHEN", "OTHER",
                name="roomtype",
                create_type=False,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("subjects", "required_room_type")
