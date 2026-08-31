"""add event engagement references

Revision ID: e6f7a8b9c012
Revises: d5e6f7a8b901
Create Date: 2026-08-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision: str = "e6f7a8b9c012"
down_revision: str | Sequence[str] | None = "d5e6f7a8b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("contributions") as batch:
        batch.add_column(sa.Column("event_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_contributions_event_id", "events", ["event_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_contributions_event_id", "contributions", ["event_id"])
    with op.batch_alter_table("badge_awards") as batch:
        batch.add_column(sa.Column("event_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_badge_awards_event_id", "events", ["event_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_badge_awards_event_id", "badge_awards", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_badge_awards_event_id", table_name="badge_awards")
    with op.batch_alter_table("badge_awards") as batch:
        batch.drop_constraint("fk_badge_awards_event_id", type_="foreignkey")
        batch.drop_column("event_id")
    op.drop_index("ix_contributions_event_id", table_name="contributions")
    with op.batch_alter_table("contributions") as batch:
        batch.drop_constraint("fk_contributions_event_id", type_="foreignkey")
        batch.drop_column("event_id")
