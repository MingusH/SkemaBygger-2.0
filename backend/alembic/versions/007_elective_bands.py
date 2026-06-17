"""add elective_bands, elective_offerings; schedule_entries elective support

Revision ID: 007
Revises: 006
Create Date: 2026-06-16
"""
from typing import Sequence, Union
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE electivebandtype AS ENUM ('PRACTICAL', 'LOCAL');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("DROP TABLE IF EXISTS elective_offerings")
    op.execute("DROP TABLE IF EXISTS elective_bands")

    op.execute("""
        CREATE TABLE elective_bands (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            grade_level INTEGER NOT NULL,
            band_type electivebandtype NOT NULL,
            name VARCHAR(200) NOT NULL,
            hours_per_week INTEGER NOT NULL,
            requires_consecutive BOOLEAN NOT NULL DEFAULT true,
            draws_timebank BOOLEAN NOT NULL DEFAULT false,
            academic_year VARCHAR(9) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE elective_offerings (
            id SERIAL PRIMARY KEY,
            band_id INTEGER NOT NULL REFERENCES elective_bands(id) ON DELETE CASCADE,
            subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
            teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
            room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE
        )
    """)

    # schedule_entries: an entry is now EITHER an assignment OR an elective offering.
    op.execute("ALTER TABLE schedule_entries ALTER COLUMN assignment_id DROP NOT NULL")
    op.execute("ALTER TABLE schedule_entries ADD COLUMN IF NOT EXISTS elective_offering_id INTEGER")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE schedule_entries
            ADD CONSTRAINT schedule_entries_elective_offering_id_fkey
            FOREIGN KEY (elective_offering_id) REFERENCES elective_offerings(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE schedule_entries
            ADD CONSTRAINT ck_entry_assignment_xor_offering
            CHECK ((assignment_id IS NULL) <> (elective_offering_id IS NULL));
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE schedule_entries DROP CONSTRAINT IF EXISTS ck_entry_assignment_xor_offering")
    op.execute("ALTER TABLE schedule_entries DROP CONSTRAINT IF EXISTS schedule_entries_elective_offering_id_fkey")
    op.execute("ALTER TABLE schedule_entries DROP COLUMN IF EXISTS elective_offering_id")
    # Note: leaves assignment_id nullable (safe; rows without it were elective-only).
    op.execute("DROP TABLE IF EXISTS elective_offerings")
    op.execute("DROP TABLE IF EXISTS elective_bands")
    op.execute("DROP TYPE IF EXISTS electivebandtype")
