"""Private task evidence metadata; storage keys are never participant API URLs."""
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class TaskAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_attachments"
    assignment_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("task_assignments.id", ondelete="RESTRICT"), index=True)
    owner_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
