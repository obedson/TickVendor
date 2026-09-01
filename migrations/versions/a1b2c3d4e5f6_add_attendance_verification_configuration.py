"""add attendance verification configuration"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f7a8b9c0d123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("max_peer_confirmations", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("peer_confirmation_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("required_verification_methods", sa.JSON(), nullable=False, server_default="[]"))
    # SQLite cannot drop a server default with ALTER COLUMN; the default is only a
    # migration backfill aid and does not affect the ORM's application default.


def downgrade() -> None:
    op.drop_column("events", "required_verification_methods")
    op.drop_column("events", "peer_confirmation_deadline")
    op.drop_column("events", "max_peer_confirmations")
