"""Preserve legacy awards while adding typed evidence and platform ceilings."""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

from src.models.base import GUID

revision = "c8d9e0f12345"
down_revision = "b7c8d9e0f123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("reward_mode", sa.String(16), nullable=False, server_default="legacy_rule"))
    op.add_column("task_submissions", sa.Column("answers", sa.JSON(), nullable=False, server_default='{}'))
    op.add_column("task_submissions", sa.Column("assessment_result", sa.JSON(), nullable=False, server_default='{}'))
    op.add_column("task_submissions", sa.Column("idempotency_key", sa.String(160)))
    op.create_index("uq_task_submission_request", "task_submissions", ["idempotency_key"], unique=True)
    table = op.create_table("point_ceilings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("source_type", sa.String(64), nullable=False, unique=True),
        sa.Column("maximum_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("maximum_points >= 0", name="ck_point_ceiling_nonnegative"))
    # Preserve deployed award levels; no invented example values or demo seeding.
    connection = op.get_bind()
    if context.is_offline_mode():
        # Offline PostgreSQL scripts cannot read rows. Generate valid UUID text
        # entirely within INSERT SELECT; no live connection is needed.
        op.execute("""INSERT INTO point_ceilings (id, source_type, maximum_points, created_at, updated_at)
            SELECT CAST(CAST(md5('tickvendor-point-ceiling:' || source_type) AS uuid) AS text),
                   source_type, GREATEST(0, MAX(points)), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM point_rules GROUP BY source_type""")
    else:
        seed_existing(connection, table)
    # Preserve duplicate historical rows, leaving only the latest global active.
    op.execute("""UPDATE point_rules SET is_active = false WHERE id IN (
        SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY source_type ORDER BY updated_at DESC, id DESC) AS n
        FROM point_rules WHERE community_id IS NULL AND is_active = true) ranked WHERE n > 1)""")
    op.create_index("uq_active_global_point_rule", "point_rules", ["source_type"], unique=True,
        sqlite_where=sa.text("community_id IS NULL AND is_active = 1"),
        postgresql_where=sa.text("community_id IS NULL AND is_active = true"))


def seed_existing(connection, table):
    rows = connection.execute(sa.text("SELECT source_type, MAX(points) AS maximum FROM point_rules GROUP BY source_type")).mappings()
    for row in rows:
        connection.execute(table.insert().values(id=uuid4(), source_type=row['source_type'],
            maximum_points=max(0, row['maximum']), created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))


def downgrade():
    op.drop_index("uq_active_global_point_rule", "point_rules")
    op.drop_table("point_ceilings")
    op.drop_index("uq_task_submission_request", "task_submissions")
    for name in ("answers", "assessment_result", "idempotency_key"):
        op.drop_column("task_submissions", name)
    op.drop_column("tasks", "reward_mode")
