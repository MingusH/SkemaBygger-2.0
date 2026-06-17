import enum
from datetime import datetime
from sqlalchemy import String, Boolean, Enum, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    VIEWER = "VIEWER"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school_memberships: Mapped[list["SchoolMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    personal_access_tokens: Mapped[list["PersonalAccessToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SchoolMember(Base):
    __tablename__ = "school_members"
    __table_args__ = (UniqueConstraint("school_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), default=UserRole.VIEWER)

    school: Mapped["School"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="school_memberships")


class PersonalAccessToken(Base):
    """A long-lived, revocable API token a user pastes into an MCP client (e.g. Claude
    Desktop). Only the SHA-256 hash is stored; the plaintext is shown once at creation.
    Deleting the row revokes it. expires_at is optional (NULL = no expiry)."""
    __tablename__ = "personal_access_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16))  # first chars, for display only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="personal_access_tokens")
