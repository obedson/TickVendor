"""scheduled notification work items

Revision ID: c8d9e0f1a2b3
Revises: a1b2c3d4e5f6
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_notifications",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("community_id", sa.CHAR(length=36), nullable=True),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "RETRYABLE", "DELIVERED", "FAILED", name="schedulednotificationstatus", native_enum=False, length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_scheduled_notifications_due", "scheduled_notifications", ["status", "scheduled_at"])
    op.create_index("ix_scheduled_notifications_tenant", "scheduled_notifications", ["community_id", "status"])
    op.create_index("ix_scheduled_notifications_scheduled_at", "scheduled_notifications", ["scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_notifications_scheduled_at", table_name="scheduled_notifications")
    op.drop_index("ix_scheduled_notifications_tenant", table_name="scheduled_notifications")
    op.drop_index("ix_scheduled_notifications_due", table_name="scheduled_notifications")
    op.drop_table("scheduled_notifications")
