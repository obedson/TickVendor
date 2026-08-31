"""Community tenancy and membership models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.base import GUID, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.organization import Organization


class MembershipRole(str, enum.Enum):
    MEMBER = "member"
    ORGANIZER = "organizer"
    ADMIN = "admin"


class MembershipStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LEFT = "left"


class Community(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "communities"
    __table_args__ = (
        Index("ix_communities_org_active", "organization_id", "is_active"),
        Index("ix_communities_search_name", "is_public", "is_active", "name"),
    )

    organization_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="communities")
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="community", cascade="all, delete-orphan"
    )


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_membership_community_user"),
        Index("ix_memberships_user_status", "user_id", "status"),
    )

    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, native_enum=False, length=16),
        default=MembershipRole.MEMBER,
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=16),
        default=MembershipStatus.ACTIVE,
        nullable=False,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    community: Mapped[Community] = relationship(back_populates="memberships")
