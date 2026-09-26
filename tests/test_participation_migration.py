"""Upgrade the actual preceding revision without changing historical meaning."""
from io import StringIO

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import settings
from tests.test_google_auth_migration import test_populated_auth_upgrade as populate


def test_populated_participation_upgrade(tmp_path, monkeypatch):
    populate(tmp_path, monkeypatch)
    engine = sa.create_engine(settings.database_url)
    metadata = sa.MetaData(); metadata.reflect(engine)
    names = [name for name in metadata.tables if name != 'alembic_version']
    columns = {name: ', '.join(column.name for column in metadata.tables[name].columns) for name in names}
    with engine.connect() as connection:
        before = {name: connection.execute(sa.text(f'SELECT {columns[name]} FROM {name}')).all() for name in names}
    config = Config('alembic.ini')
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ['0a1b2c3d4e5f']
    revisions = list(script.walk_revisions())
    assert len({r.revision for r in revisions}) == len(revisions)
    command.upgrade(config, 'e0f1a2b34567')
    with engine.connect() as connection:
        for name in names:
            assert connection.execute(sa.text(f'SELECT {columns[name]} FROM {name}')).all() == before[name], name
        assert connection.execute(sa.text('PRAGMA foreign_key_check')).all() == []
        assert connection.execute(sa.text('SELECT attachment_ids, location_evidence FROM task_submissions')).one() == ('[]', '{}')
        assert connection.execute(sa.text('SELECT COUNT(*) FROM promotions')).scalar_one() == 0
        assert connection.execute(sa.text('SELECT COUNT(*) FROM task_attachments')).scalar_one() == 0
    assert any(i['name'] == 'ix_promotions_delivery' for i in sa.inspect(engine).get_indexes('promotions'))
    assert len(sa.inspect(engine).get_foreign_keys('task_attachments')) == 2
    command.downgrade(config, 'd9e0f1a23456')
    command.upgrade(config, 'e0f1a2b34567')
    engine.dispose()


def test_postgresql_participation_sql(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(settings, 'database_url', 'postgresql://migration-test/unused')
    command.upgrade(Config('alembic.ini', output_buffer=output), 'd9e0f1a23456:e0f1a2b34567', sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE task_attachments' in sql and 'CREATE TABLE promotions' in sql
    assert "DEFAULT '[]' NOT NULL" in sql and 'ADD COLUMN lga' in sql
    assert 'point_rules' not in sql and 'impact_transactions' not in sql
    assert 'DELETE FROM' not in sql and 'DROP TABLE' not in sql
