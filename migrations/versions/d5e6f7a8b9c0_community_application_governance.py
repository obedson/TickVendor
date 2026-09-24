"""Add reviewed community lifecycle and retire legacy platform roles.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""

import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    context = op.get_context()
    sqlite = context.dialect.name == "sqlite" and not context.as_sql
    if sqlite:
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("communities") as batch:
            batch.add_column(
                sa.Column(
                    "lifecycle_status",
                    sa.String(24),
                    nullable=False,
                    server_default="ACTIVE",
                )
            )
            batch.add_column(
                sa.Column(
                    "submitted_by_id",
                    GUID(),
                    sa.ForeignKey(
                        "users.id",
                        name="fk_communities_submitted_by_user",
                        ondelete="SET NULL",
                    ),
                    nullable=True,
                )
            )
            batch.add_column(
                sa.Column(
                    "reviewed_by_id",
                    GUID(),
                    sa.ForeignKey(
                        "users.id",
                        name="fk_communities_reviewed_by_user",
                        ondelete="SET NULL",
                    ),
                    nullable=True,
                )
            )
            batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
            batch.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
            batch.create_index("ix_communities_submitted_by_id", ["submitted_by_id"])

    # Existing active/suspended communities keep their deployed meaning. Their organization
    # owner is retained as provenance, but no membership or historical authority is rewritten.
        op.execute(
            sa.text(
                "UPDATE communities SET lifecycle_status = "
                "CASE WHEN is_active THEN 'ACTIVE' ELSE 'SUSPENDED' END"
            )
        )
        op.execute(
            sa.text(
                "UPDATE communities SET submitted_by_id = "
                "(SELECT organizations.owner_id FROM organizations "
                "WHERE organizations.id = communities.organization_id) "
                "WHERE submitted_by_id IS NULL"
            )
        )

    # Community authority is membership-scoped. These unused platform-wide roles previously
    # carried no community permissions, so normalize them without touching membership rows.
        op.execute(
            sa.text(
                "UPDATE users SET role = 'PARTICIPANT' "
                "WHERE role IN ('ORGANIZER', 'COMMUNITY_ADMIN')"
            )
        )
        if sqlite and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first():
            raise RuntimeError("Foreign-key integrity failed after community lifecycle migration")
    finally:
        if sqlite:
            with context.autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    # Legacy platform roles cannot be reconstructed safely because they were not authoritative.
    context = op.get_context()
    sqlite = context.dialect.name == "sqlite" and not context.as_sql
    if sqlite:
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("communities") as batch:
            batch.drop_index("ix_communities_submitted_by_id")
            batch.drop_column("review_reason")
            batch.drop_column("reviewed_at")
            batch.drop_column("reviewed_by_id")
            batch.drop_column("submitted_by_id")
            batch.drop_column("lifecycle_status")
        if sqlite and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first():
            raise RuntimeError("Foreign-key integrity failed after community lifecycle downgrade")
    finally:
        if sqlite:
            with context.autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")
