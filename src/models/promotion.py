"""Auditable editorial and sponsored placements; content remains authoritative."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Promotion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_promotion_schedule"),
        CheckConstraint("classification IN ('featured', 'sponsored')", name="ck_promotion_classification"),
        CheckConstraint("content_type IN ('community', 'event', 'opportunity', 'task')", name="ck_promotion_content_type"),
        CheckConstraint("surface IN ('home', 'discover', 'event-detail', 'opportunities', 'communities', 'tasks')", name="ck_promotion_surface"),
        Index("ix_promotions_delivery", "surface", "is_active", "starts_at", "ends_at"),
    )
    content_type: Mapped[str] = mapped_column(String(20))
    content_id: Mapped[UUID] = mapped_column(GUID())
    classification: Mapped[str] = mapped_column(String(12))
    surface: Mapped[str] = mapped_column(String(24))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="RESTRICT"))
