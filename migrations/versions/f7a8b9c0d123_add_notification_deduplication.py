"""add notification deduplication

Revision ID: f7a8b9c0d123
Revises: e6f7a8b9c012
Create Date: 2026-08-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d123"
down_revision: str | Sequence[str] | None = "e6f7a8b9c012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("deduplication_key", sa.String(200), nullable=True))
    op.create_index("ix_notifications_deduplication_key", "notifications", ["deduplication_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_notifications_deduplication_key", table_name="notifications")
    op.drop_column("notifications", "deduplication_key")
