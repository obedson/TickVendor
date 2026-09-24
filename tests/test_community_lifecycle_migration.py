"""Community lifecycle migration preserves deployed tenancy and authority data."""

from io import StringIO

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import settings
from tests.test_task_evidence_migration import test_populated_upgrade_preserves_history


def test_populated_upgrade_adds_lifecycle_without_rewriting_memberships(tmp_path, monkeypatch):
    test_populated_upgrade_preserves_history(tmp_path, monkeypatch)
    config = Config("alembic.ini")
    command.upgrade(config, "c4d5e6f7a8b9")
    engine = sa.create_engine(settings.database_url)
    with engine.begin() as connection:
        community_id, organization_id = connection.execute(
            sa.text("SELECT id, organization_id FROM communities ORDER BY id LIMIT 1")
        ).one()
        owner_id = connection.execute(
            sa.text("SELECT owner_id FROM organizations WHERE id=:id"), {"id": organization_id}
        ).scalar_one()
        membership_rows = connection.execute(
            sa.text("SELECT id, community_id, user_id, role, status FROM memberships ORDER BY id")
        ).all()
        connection.execute(sa.text("UPDATE users SET role='COMMUNITY_ADMIN' WHERE id=:id"), {"id": owner_id})
    engine.dispose()

    command.upgrade(config, "head")
    engine = sa.create_engine(settings.database_url)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "d5e6f7a8b9c0"
        lifecycle, submitted_by = connection.execute(
            sa.text("SELECT lifecycle_status, submitted_by_id FROM communities WHERE id=:id"),
            {"id": community_id},
        ).one()
        assert lifecycle == "ACTIVE"
        assert submitted_by == owner_id
        assert connection.execute(sa.text("SELECT role FROM users WHERE id=:id"), {"id": owner_id}).scalar_one() == "PARTICIPANT"
        assert connection.execute(
            sa.text("SELECT id, community_id, user_id, role, status FROM memberships ORDER BY id")
        ).all() == membership_rows
    engine.dispose()
    command.downgrade(config, "c4d5e6f7a8b9")
    engine = sa.create_engine(settings.database_url)
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT id, community_id, user_id, role, status FROM memberships ORDER BY id")
        ).all() == membership_rows
    engine.dispose()
    command.upgrade(config, "head")


def test_community_lifecycle_revision_and_postgresql_sql(monkeypatch):
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["d5e6f7a8b9c0"]
    assert script.get_revision("d5e6f7a8b9c0").down_revision == "c4d5e6f7a8b9"
    output = StringIO()
    monkeypatch.setattr(settings, "database_url", "postgresql://migration-test/unused")
    command.upgrade(Config("alembic.ini", output_buffer=output), "c4d5e6f7a8b9:d5e6f7a8b9c0", sql=True)
    sql = output.getvalue()
    assert "lifecycle_status" in sql
    assert "submitted_by_id" in sql
    assert "UPDATE users SET role = 'PARTICIPANT'" in sql
    assert "UPDATE memberships" not in sql
