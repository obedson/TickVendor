"""add activity opportunities and registrations"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_opportunities",
        sa.Column("community_id", GUID(), nullable=False), sa.Column("created_by_id", GUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("activity_type", sa.String(80), nullable=False), sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(500)), sa.Column("capacity", sa.Integer()), sa.Column("members_only", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("id", GUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_opportunities_discovery", "activity_opportunities", ["status", "starts_at"])
    op.create_index("ix_activity_opportunities_community_status", "activity_opportunities", ["community_id", "status"])
    op.create_index("ix_activity_opportunities_deleted_at", "activity_opportunities", ["deleted_at"])
    op.create_table(
        "opportunity_registrations",
        sa.Column("opportunity_id", GUID(), nullable=False), sa.Column("participant_id", GUID(), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("verified_by_id", GUID()),
        sa.Column("id", GUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["activity_opportunities.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["participant_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("opportunity_id", "participant_id", name="uq_opportunity_registration_participant"),
    )
    op.create_index("ix_opportunity_registrations_opportunity_status", "opportunity_registrations", ["opportunity_id", "status"])
    with op.batch_alter_table("activities") as batch:
        batch.add_column(sa.Column("opportunity_id", GUID(), nullable=True))
        batch.create_foreign_key("fk_activities_opportunity_id", "activity_opportunities", ["opportunity_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_activities_opportunity_id", "activities", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_opportunity_registrations_opportunity_status", table_name="opportunity_registrations")
    op.drop_table("opportunity_registrations")
    op.drop_index("ix_activities_opportunity_id", table_name="activities")
    with op.batch_alter_table("activities") as batch:
        batch.drop_constraint("fk_activities_opportunity_id", type_="foreignkey")
        batch.drop_column("opportunity_id")
    op.drop_index("ix_activity_opportunities_community_status", table_name="activity_opportunities")
    op.drop_index("ix_activity_opportunities_discovery", table_name="activity_opportunities")
    op.drop_index("ix_activity_opportunities_deleted_at", table_name="activity_opportunities")
    op.drop_table("activity_opportunities")