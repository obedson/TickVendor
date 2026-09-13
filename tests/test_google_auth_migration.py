"""Upgrade from staging revision without rewriting historical identity or rewards."""
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import settings
from src.database import Base
from tests.test_task_evidence_migration import (
    test_populated_upgrade_preserves_history as populate_history,
)


def test_populated_auth_upgrade(tmp_path, monkeypatch):
    populate_history(tmp_path, monkeypatch)
    engine = sa.create_engine(settings.database_url)
    metadata = sa.MetaData(); metadata.reflect(engine)
    # Include CASCADE, SET NULL and RESTRICT dependents, not just table counts.
    def populate(connection, name):
        table = metadata.tables[name]
        existing = connection.execute(sa.select(table.c.id).limit(1)).scalar()
        if existing:
            return existing
        row = {'id': str(uuid4())}
        for col in table.columns:
            if col.name in row:
                continue
            fk = next(iter(col.foreign_keys), None)
            if fk and (not col.nullable or fk.column.table.name == 'users'):
                row[col.name] = populate(connection, fk.column.table.name)
            elif col.nullable or col.server_default:
                continue
            else:
                model_type = Base.metadata.tables[name].c[col.name].type
                row[col.name] = (model_type.enums[0] if isinstance(model_type, sa.Enum)
                                 else datetime(2026, 9, 1, tzinfo=UTC) if isinstance(col.type, sa.DateTime)
                                 else {} if isinstance(col.type, sa.JSON)
                                 else True if isinstance(col.type, sa.Boolean)
                                 else 1 if isinstance(col.type, (sa.Integer, sa.Numeric, sa.Float))
                                 else 'NGN' if col.name == 'currency' else 'fixture')
        connection.execute(table.insert().values(**row))
        return row['id']
    with engine.begin() as connection:
        for name in ['profiles', 'memberships', 'auth_sessions', 'auth_tokens', 'tickets', 'payments',
                     'attendances', 'attendance_verifications', 'badge_awards', 'milestone_awards',
                     'achievement_awards', 'rank_progressions', 'audit_logs', 'notifications']:
            populate(connection, name)
    names = [name for name in metadata.tables if name != 'alembic_version']
    with engine.connect() as connection:
        before = {name: connection.execute(sa.text(f'SELECT * FROM {name}')).all() for name in names}
    config = Config('alembic.ini')
    assert ScriptDirectory.from_config(config).get_heads() == ['d9e0f1a23456']
    command.upgrade(config, 'head')
    with engine.connect() as connection:
        for name in names:
            assert connection.execute(sa.text(f'SELECT * FROM {name}')).all() == before[name]
        assert connection.execute(sa.text('PRAGMA foreign_key_check')).all() == []
    assert next(c for c in sa.inspect(engine).get_columns('users') if c['name'] == 'password_hash')['nullable']
    assert {tuple(c['column_names']) for c in sa.inspect(engine).get_unique_constraints('external_identities')} == {('provider', 'provider_subject'), ('user_id', 'provider')}
    command.downgrade(config, 'c8d9e0f12345')
    command.upgrade(config, 'head')
    engine.dispose()


def test_postgresql_auth_upgrade_sql(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(settings, 'database_url', 'postgresql://migration-test/unused')
    command.upgrade(Config('alembic.ini', output_buffer=output), 'c8d9e0f12345:d9e0f1a23456', sql=True)
    sql = output.getvalue()
    assert 'ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL' in sql
    assert 'CREATE TABLE external_identities' in sql and 'CREATE TABLE google_auth_flows' in sql
    assert 'impact_transactions' not in sql and 'point_rules' not in sql and 'DELETE FROM' not in sql
