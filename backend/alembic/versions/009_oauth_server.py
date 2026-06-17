"""add OAuth authorization-server tables (clients, auth codes, refresh tokens)

Revision ID: 009
Revises: 008
Create Date: 2026-06-17
"""
from typing import Sequence, Union
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth_clients (
            client_id VARCHAR(255) PRIMARY KEY,
            client_secret VARCHAR(255),
            client_data TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth_auth_codes (
            code VARCHAR(128) PRIMARY KEY,
            client_id VARCHAR(255) NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            redirect_uri VARCHAR(2048) NOT NULL,
            redirect_uri_provided_explicitly BOOLEAN NOT NULL DEFAULT true,
            scopes VARCHAR(1024) NOT NULL DEFAULT '',
            code_challenge VARCHAR(255),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_auth_codes_client_id ON oauth_auth_codes (client_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
            token_hash VARCHAR(64) PRIMARY KEY,
            client_id VARCHAR(255) NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            scopes VARCHAR(1024) NOT NULL DEFAULT '',
            expires_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_refresh_tokens_client_id ON oauth_refresh_tokens (client_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS oauth_refresh_tokens")
    op.execute("DROP TABLE IF EXISTS oauth_auth_codes")
    op.execute("DROP TABLE IF EXISTS oauth_clients")
