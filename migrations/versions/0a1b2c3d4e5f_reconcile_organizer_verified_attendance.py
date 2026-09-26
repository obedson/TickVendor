"""Reconcile attendance status with valid organizer verification evidence.

Revision ID: 0a1b2c3d4e5f
Revises: f7a8b9c0d1e2
"""

import sqlalchemy as sa
from alembic import op

revision = "0a1b2c3d4e5f"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLAlchemy persists Enum member names. Organizer approval is an explicit human
    # override, so a valid organizer signal authoritatively implies ORGANIZER_VERIFIED.
    # Restrict the repair to stale CHECKED_IN rows; no evidence, points, tickets, or
    # historical transactions are rewritten.
    op.execute(sa.text(
        'UPDATE attendances AS attendance '
        'SET status = \'ORGANIZER_VERIFIED\', confidence_score = 100 '
        "WHERE attendance.status = 'CHECKED_IN' "
        'AND EXISTS ('
        'SELECT 1 FROM attendance_verifications AS verification '
        'WHERE verification.attendance_id = attendance.id '
        "AND verification.method = 'ORGANIZER' "
        'AND verification.is_valid IS TRUE'
        ')'
    ))


def downgrade() -> None:
    # This repairs derived state from authoritative evidence. Reintroducing the
    # contradiction on downgrade would be unsafe, so the data correction is retained.
    pass
