"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_enum(name: str, values: list[str]) -> None:
    vals = ", ".join(f"'{v}'" for v in values)
    op.execute(f"""
        DO $$ BEGIN
            CREATE TYPE {name} AS ENUM ({vals});
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)


def upgrade() -> None:
    # --- Enum types (idempotent) ---
    _create_enum("userrole", ["ADMIN", "VIEWER"])
    _create_enum("subjectcategory", ["humanistisk", "naturfag", "praktisk_musisk", "valgfag"])
    _create_enum("roomtype", ["STANDARD", "GYM", "SCIENCE_LAB", "COMPUTER", "MUSIC", "WORKSHOP", "KITCHEN", "OTHER"])
    _create_enum("constrainttype", ["HARD", "SOFT"])
    _create_enum("entitytype", ["TEACHER", "CLASS", "SUBJECT", "ROOM"])
    _create_enum("preferencetype", ["PREFER_MORNING", "AVOID_LAST_PERIOD", "NO_ISOLATED_LESSONS", "MAX_DAILY_HOURS", "SUBJECT_SPREAD"])
    _create_enum("schedulestatus", ["DRAFT", "GENERATING", "COMPLETE", "FAILED", "PUBLISHED"])

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- schools ---
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(20), nullable=False),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("periods_per_day", sa.Integer, nullable=False),
        sa.Column("days_per_week", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- school_members ---
    op.create_table(
        "school_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", PgEnum(name="userrole", create_type=False), nullable=False, server_default="VIEWER"),
        sa.UniqueConstraint("school_id", "user_id"),
    )

    # --- time_slots ---
    op.create_table(
        "time_slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("period_number", sa.Integer, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("label", sa.String(50), nullable=True),
        sa.UniqueConstraint("school_id", "day_of_week", "period_number"),
    )

    # --- subjects ---
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(10), nullable=False),
        sa.Column("category", PgEnum(name="subjectcategory", create_type=False), nullable=False),
        sa.Column("color_hex", sa.String(7), nullable=True),
        sa.Column("requires_special_room", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_elective_slot", sa.Boolean, nullable=False, server_default="false"),
    )

    # --- elective_slot_meta ---
    op.create_table(
        "elective_slot_meta",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("slot_key", sa.String(50), nullable=False),
        sa.Column("has_exam", sa.Boolean, nullable=False, server_default="false"),
    )

    # --- ministry_hours ---
    op.create_table(
        "ministry_hours",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grade", sa.Integer, nullable=False),
        sa.Column("hours_per_week", sa.Float, nullable=False),
        sa.UniqueConstraint("subject_id", "grade"),
    )

    # --- rooms ---
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(10), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("room_type", PgEnum(name="roomtype", create_type=False), nullable=False, server_default="STANDARD"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # --- teachers ---
    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(10), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("max_hours_per_week", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- teacher_subjects ---
    op.create_table(
        "teacher_subjects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("teacher_id", "subject_id"),
    )

    # --- student_classes ---
    op.create_table(
        "student_classes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("grade_level", sa.Integer, nullable=False),
        sa.Column("student_count", sa.Integer, nullable=False),
        sa.Column("home_room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # --- assignments ---
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_class_id", sa.Integer, sa.ForeignKey("student_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preferred_room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("hours_per_week", sa.Integer, nullable=False),
        sa.Column("requires_consecutive", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("min_days_between_lessons", sa.Integer, nullable=True),
        sa.Column("parallel_group_id", sa.Integer, nullable=True),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.UniqueConstraint("teacher_id", "subject_id", "student_class_id", "academic_year"),
    )

    # --- teacher_unavailabilities ---
    op.create_table(
        "teacher_unavailabilities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_slot_id", sa.Integer, sa.ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("constraint_type", PgEnum(name="constrainttype", create_type=False), nullable=False, server_default="HARD"),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.UniqueConstraint("teacher_id", "time_slot_id"),
    )

    # --- room_unavailabilities ---
    op.create_table(
        "room_unavailabilities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_slot_id", sa.Integer, sa.ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.UniqueConstraint("room_id", "time_slot_id"),
    )

    # --- class_unavailabilities ---
    op.create_table(
        "class_unavailabilities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_class_id", sa.Integer, sa.ForeignKey("student_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_slot_id", sa.Integer, sa.ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.UniqueConstraint("student_class_id", "time_slot_id"),
    )

    # --- scheduling_preferences ---
    op.create_table(
        "scheduling_preferences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", PgEnum(name="entitytype", create_type=False), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("preference_type", PgEnum(name="preferencetype", create_type=False), nullable=False),
        sa.Column("value", sa.JSON, nullable=True),
        sa.Column("weight", sa.Integer, nullable=False, server_default="5"),
    )

    # --- schedules ---
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("status", PgEnum(name="schedulestatus", create_type=False), nullable=False, server_default="DRAFT"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algorithm_params", sa.JSON, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- schedule_entries ---
    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("schedule_id", sa.Integer, sa.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_id", sa.Integer, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_slot_id", sa.Integer, sa.ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_locked", sa.Boolean, nullable=False, server_default="false"),
        sa.UniqueConstraint("schedule_id", "time_slot_id", "room_id"),
    )


def downgrade() -> None:
    op.drop_table("schedule_entries")
    op.drop_table("schedules")
    op.drop_table("scheduling_preferences")
    op.drop_table("class_unavailabilities")
    op.drop_table("room_unavailabilities")
    op.drop_table("teacher_unavailabilities")
    op.drop_table("assignments")
    op.drop_table("student_classes")
    op.drop_table("teacher_subjects")
    op.drop_table("teachers")
    op.drop_table("rooms")
    op.drop_table("ministry_hours")
    op.drop_table("elective_slot_meta")
    op.drop_table("subjects")
    op.drop_table("time_slots")
    op.drop_table("school_members")
    op.drop_table("schools")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS schedulestatus")
    op.execute("DROP TYPE IF EXISTS preferencetype")
    op.execute("DROP TYPE IF EXISTS entitytype")
    op.execute("DROP TYPE IF EXISTS constrainttype")
    op.execute("DROP TYPE IF EXISTS roomtype")
    op.execute("DROP TYPE IF EXISTS subjectcategory")
    op.execute("DROP TYPE IF EXISTS userrole")
