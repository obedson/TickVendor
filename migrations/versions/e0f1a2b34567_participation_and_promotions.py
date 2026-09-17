"""Add private task evidence, structured venue LGA and real promotions.

Historical task configuration, rules and Impact transactions are untouched.
"""
import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision = "e0f1a2b34567"
down_revision = "d9e0f1a23456"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("venues", sa.Column("lga", sa.String(120), nullable=True))
    op.add_column("task_submissions", sa.Column("attachment_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("task_submissions", sa.Column("location_evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_table("task_attachments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("assignment_id", GUID(), sa.ForeignKey("task_assignments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False, unique=True),
        sa.Column("filename", sa.String(160), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_task_attachments_assignment_id", "task_attachments", ["assignment_id"])
    op.create_index("ix_task_attachments_owner_id", "task_attachments", ["owner_id"])
    op.create_table("promotions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content_id", GUID(), nullable=False),
        sa.Column("classification", sa.String(12), nullable=False),
        sa.Column("surface", sa.String(24), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_promotion_schedule"),
        sa.CheckConstraint("classification IN ('featured', 'sponsored')", name="ck_promotion_classification"),
        sa.CheckConstraint("content_type IN ('community', 'event', 'opportunity', 'task')", name="ck_promotion_content_type"),
        sa.CheckConstraint("surface IN ('home', 'discover', 'event-detail', 'opportunities', 'communities', 'tasks')", name="ck_promotion_surface"))
    op.create_index("ix_promotions_delivery", "promotions", ["surface", "is_active", "starts_at", "ends_at"])


def downgrade():
    # Uploaded evidence and campaign/audit history need an explicit recovery plan.
    for table in ("task_attachments", "promotions"):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError("Participation/promotion data exists; preserve evidence and plan recovery before downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM task_submissions WHERE CAST(location_evidence AS VARCHAR) <> '{}' OR CAST(attachment_ids AS VARCHAR) <> '[]'")).scalar():
        raise RuntimeError("Submission evidence exists; downgrade would lose history")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM venues WHERE lga IS NOT NULL")).scalar():
        raise RuntimeError("Structured venue data exists; downgrade would lose history")
    op.drop_table("promotions")
    op.drop_table("task_attachments")
    op.drop_column("task_submissions", "location_evidence")
    op.drop_column("task_submissions", "attachment_ids")
    op.drop_column("venues", "lga")
