"""Membership access, independent moderation and personal archives."""
import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision = "b7c8d9e0f123"
down_revision = "9f0a1b2c3d4e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_memberships_community_status", "memberships", ["community_id", "status"])
    op.add_column("communities", sa.Column("membership_access", sa.String(24), nullable=False, server_default="INVITE_ONLY"))
    for table in ("events", "activity_opportunities", "tasks"):
        op.add_column(table, sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index(f"ix_{table}_suspended", table, ["is_suspended"])
    op.create_table("personal_archives",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(24), nullable=False),
        sa.Column("item_id", GUID(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "item_type", "item_id", name="uq_personal_archive_owner_item"),
        sa.CheckConstraint("item_type IN ('notification', 'ticket', 'task', 'opportunity')", name="ck_personal_archive_type"),
    )
    op.create_index("ix_personal_archive_owner_type", "personal_archives", ["user_id", "item_type"])


def downgrade():
    op.drop_index("ix_memberships_community_status", "memberships")
    op.drop_table("personal_archives")
    for table in ("events", "activity_opportunities", "tasks"):
        op.drop_index(f"ix_{table}_suspended", table)
        op.drop_column(table, "is_suspended")
    op.drop_column("communities", "membership_access")
