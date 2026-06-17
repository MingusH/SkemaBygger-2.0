"""add personal_access_tokens

Revision ID: 008
Revises: 007
Create Date: 2026-06-17
"""
from typing import Sequence, Union
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS personal_access_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            token_hash VARCHAR(64) NOT NULL,
            prefix VARCHAR(16) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_used_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_personal_access_tokens_token_hash ON personal_access_tokens (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_user_id ON personal_access_tokens (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS personal_access_tokens")
