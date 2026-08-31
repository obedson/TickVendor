"""add search indexes

Revision ID: a4f3d2c1b098
Revises: 66fb987e6019
Create Date: 2026-08-31
"""
from collections.abc import Sequence

from alembic import op

revision: str = "a4f3d2c1b098"
down_revision: str | Sequence[str] | None = "66fb987e6019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_events_search_title", "events", ["status", "title"])
    op.create_index("ix_communities_search_name", "communities", ["is_public", "is_active", "name"])
    op.create_index("ix_profiles_search_identity", "profiles", ["visibility", "display_name"])
    op.create_index("ix_tasks_search_title", "tasks", ["community_id", "is_active", "title"])


def downgrade() -> None:
    op.drop_index("ix_tasks_search_title", table_name="tasks")
    op.drop_index("ix_profiles_search_identity", table_name="profiles")
    op.drop_index("ix_communities_search_name", table_name="communities")
    op.drop_index("ix_events_search_title", table_name="events")
