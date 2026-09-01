"""add task evidence attachments"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("attachments", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("task_submissions", sa.Column("evidence_attachments", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("task_submissions", "evidence_attachments")
    op.drop_column("tasks", "attachments")
