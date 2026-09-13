"""User identity and profile models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformRole(str, enum.Enum):
    PARTICIPANT = "participant"
    ORGANIZER = "organizer"
    COMMUNITY_ADMIN = "community_admin"
    SUPER_ADMIN = "super_admin"


class ProfileVisibility(str, enum.Enum):
    PUBLIC = "public"
    MEMBERS = "members"
    PRIVATE = "private"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[PlatformRole] = mapped_column(
        Enum(PlatformRole, native_enum=False, length=32),
        default=PlatformRole.PARTICIPANT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Profile] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (Index("ix_profiles_search_identity", "visibility", "display_name"),)

    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(2048))
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    interests: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    visibility: Mapped[ProfileVisibility] = mapped_column(
        Enum(ProfileVisibility, native_enum=False, length=16),
        default=ProfileVisibility.PUBLIC,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="profile")
