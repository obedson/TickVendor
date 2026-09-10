"""add task_type and task_config columns

Revision ID: 9f0a1b2c3d4e
Revises: f1a2b3c4d5e6
Create Date: 2026-09-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f0a1b2c3d4e"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_type",
                sa.String(length=32),
                nullable=False,
                server_default="general",
            )
        )
        batch_op.add_column(
            sa.Column(
                "task_config",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
        batch_op.add_column(
            sa.Column(
                "required_evidence_types",
                sa.JSON(),
                nullable=False,
                server_default='["text"]',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("required_evidence_types")
        batch_op.drop_column("task_config")
        batch_op.drop_column("task_type")
