"""Persistence for the self-hosted OAuth 2.1 authorization server that backs MCP
client connections (e.g. Claude Desktop). Identity stays the existing User table —
these tables only hold OAuth protocol state.

- OAuthClient: dynamically-registered clients (RFC 7591). Claude registers once.
- OAuthAuthCode: short-lived, one-time authorization codes (deleted on exchange).
- OAuthRefreshToken: long-lived, revocable, rotated refresh tokens (hash stored).

Access tokens are NOT stored — they're short-lived JWTs signed with secret_key and
verified statelessly (see app/services/oauth_provider.py)."""
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    client_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_data: Mapped[str] = mapped_column(Text)  # full OAuthClientInformationFull JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OAuthAuthCode(Base):
    __tablename__ = "oauth_auth_codes"

    code: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(255), index=True)
    user_email: Mapped[str] = mapped_column(String(255))
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    redirect_uri_provided_explicitly: Mapped[bool] = mapped_column(Boolean, default=True)
    scopes: Mapped[str] = mapped_column(String(1024), default="")  # space-separated
    code_challenge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OAuthRefreshToken(Base):
    __tablename__ = "oauth_refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(255), index=True)
    user_email: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[str] = mapped_column(String(1024), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
