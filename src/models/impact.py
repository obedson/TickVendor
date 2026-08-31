"""Auditable, idempotent Impact Point transaction model."""

import enum
from typing import Any

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class ImpactTransactionStatus(str, enum.Enum):
    PENDING = "pending"
    POSTED = "posted"
    REVERSED = "reversed"


class ImpactTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "impact_transactions"
    __table_args__ = (
        Index("ix_impact_user_status", "user_id", "status"),
        Index("ix_impact_community_created", "community_id", "created_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    community_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="RESTRICT"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[Any | None] = mapped_column(GUID())
    event_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="SET NULL")
    )
    task_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ImpactTransactionStatus] = mapped_column(
        Enum(ImpactTransactionStatus, native_enum=False, length=16),
        default=ImpactTransactionStatus.PENDING,
        nullable=False,
    )
    reversed_transaction_id: Mapped[Any | None] = mapped_column(
        GUID(), ForeignKey("impact_transactions.id", ondelete="RESTRICT")
    )
