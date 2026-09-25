"""Separate geofence distance from automatic-verification accuracy.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("geofence_max_accuracy_meters", sa.Integer(), nullable=False, server_default="50"),
    )
    # Preserve the historical rule for existing events. Organizers can tighten accuracy later
    # without changing the attendance radius or rewriting historical attendance evidence.
    op.execute(sa.text(
        "UPDATE events SET geofence_max_accuracy_meters = geofence_radius_meters "
        "WHERE geofence_enabled = true AND geofence_radius_meters IS NOT NULL"
    ))


def downgrade() -> None:
    op.drop_column("events", "geofence_max_accuracy_meters")
