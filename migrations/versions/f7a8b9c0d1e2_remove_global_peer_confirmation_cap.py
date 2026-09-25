"""Remove the incorrectly global peer confirmation cap.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("events", "max_peer_confirmations")


def downgrade() -> None:
    op.add_column("events", sa.Column("max_peer_confirmations", sa.Integer(), nullable=True))
