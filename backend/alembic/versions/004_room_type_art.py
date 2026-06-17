"""add ART room type and map Billedkunst to it

Revision ID: 004
Revises: 003
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A new enum value can't be used in the same transaction it's added, so add
    # it in its own autocommitted statement first.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE roomtype ADD VALUE IF NOT EXISTS 'ART'")

    # Reclassify existing art rooms (currently generic OTHER) so they're reserved.
    op.execute(
        "UPDATE rooms SET room_type = 'ART' "
        "WHERE room_type = 'OTHER' AND lower(name) LIKE 'billedkunst%'"
    )
    # Billedkunst must now be taught in an ART room (hard constraint).
    op.execute(
        "UPDATE subjects SET required_room_type = 'ART', requires_special_room = true "
        "WHERE lower(name) LIKE 'billedkunst%'"
    )


def downgrade() -> None:
    # Revert the data; the enum value itself can't be dropped cleanly in Postgres
    # and is left in place (harmless).
    op.execute(
        "UPDATE subjects SET required_room_type = NULL, requires_special_room = false "
        "WHERE lower(name) LIKE 'billedkunst%'"
    )
    op.execute(
        "UPDATE rooms SET room_type = 'OTHER' "
        "WHERE room_type = 'ART' AND lower(name) LIKE 'billedkunst%'"
    )
