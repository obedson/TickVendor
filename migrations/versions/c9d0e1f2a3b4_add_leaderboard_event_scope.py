"""add leaderboard event scope

Revision ID: c9d0e1f2a3b4
Revises: c8d9e0f1a2b3
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leaderboards", sa.Column("event_id", sa.CHAR(length=36), nullable=True))
    with op.batch_alter_table("leaderboards") as batch_op:
        batch_op.create_foreign_key(
            "fk_leaderboards_event_id_events", "events", ["event_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("leaderboards") as batch_op:
        batch_op.drop_constraint("fk_leaderboards_event_id_events", type_="foreignkey")
        batch_op.drop_column("event_id")
