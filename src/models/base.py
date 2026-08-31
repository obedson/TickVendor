"""Shared SQLAlchemy model types and mixins."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator[UUID]):
    """Portable UUID stored natively where possible and as CHAR(36) otherwise."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UUID | str | None, dialect) -> str | None:
        if value is None:
            return None
        return str(value if isinstance(value, UUID) else UUID(value))

    def process_result_value(self, value: str | None, dialect) -> UUID | None:
        return UUID(value) if value is not None else None


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
