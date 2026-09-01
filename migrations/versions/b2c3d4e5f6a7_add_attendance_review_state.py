"""add attendance review state"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attendances") as batch:
        batch.add_column(sa.Column("review_status", sa.String(length=16), nullable=False, server_default="open"))
        batch.add_column(sa.Column("reviewed_by_id", sa.CHAR(length=36), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("review_resolution", sa.String(length=500), nullable=True))
        batch.create_foreign_key("fk_attendances_reviewed_by", "users", ["reviewed_by_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("attendances") as batch:
        batch.drop_constraint("fk_attendances_reviewed_by", type_="foreignkey")
        batch.drop_column("review_resolution")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by_id")
        batch.drop_column("review_status")
