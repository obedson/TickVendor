"""add soft deletion

Revision ID: d5e6f7a8b901
Revises: a4f3d2c1b098
Create Date: 2026-08-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b901"
down_revision: str | Sequence[str] | None = "a4f3d2c1b098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("communities", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_communities_deleted_at", "communities", ["deleted_at"])
    op.add_column("events", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_events_deleted_at", "events", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_events_deleted_at", table_name="events")
    op.drop_column("events", "deleted_at")
    op.drop_index("ix_communities_deleted_at", table_name="communities")
    op.drop_column("communities", "deleted_at")
