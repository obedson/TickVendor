"""Per-user presentation preferences; never a domain lifecycle status."""
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, UUIDPrimaryKeyMixin


class PersonalArchive(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "personal_archives"
    __table_args__ = (
        CheckConstraint("item_type IN ('notification', 'ticket', 'task', 'opportunity')", name="ck_personal_archive_type"),
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_personal_archive_owner_item"),
        Index("ix_personal_archive_owner_type", "user_id", "item_type"),
    )
    user_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(24), nullable=False)
    item_id: Mapped[Any] = mapped_column(GUID(), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
