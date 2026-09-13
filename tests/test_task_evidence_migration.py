"""Upgrade the deployed schema with historical task/evidence/ledger data intact."""
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import settings


def test_populated_upgrade_preserves_history(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'task-migration.db').as_posix()}"
    monkeypatch.setattr(settings, 'database_url', url)
    config = Config('alembic.ini')
    assert ScriptDirectory.from_config(config).get_heads() == ['c8d9e0f12345']
    command.upgrade(config, 'b7c8d9e0f123')
    engine = sa.create_engine(url)
    metadata = sa.MetaData(); metadata.reflect(engine)
    ids = {name: str(uuid4()) for name in ['users', 'organizations', 'communities', 'tasks', 'task_assignments', 'task_submissions', 'impact_transactions']}

    def insert(connection, name, **values):
        table = metadata.tables[name]
        row = {'id': ids.get(name, str(uuid4())), **values}
        for col in table.columns:
            if col.name in row or col.nullable or col.server_default:
                continue
            row[col.name] = (datetime(2026, 9, 1, tzinfo=UTC) if isinstance(col.type, sa.DateTime)
                             else {} if isinstance(col.type, sa.JSON)
                             else True if isinstance(col.type, sa.Boolean)
                             else 0 if isinstance(col.type, sa.Integer) else 'legacy')
        connection.execute(table.insert().values(**row))

    with engine.begin() as connection:
        insert(connection, 'users', email='historical@example.com', role='PARTICIPANT')
        insert(connection, 'organizations', owner_id=ids['users'])
        insert(connection, 'communities', organization_id=ids['organizations'])
        insert(connection, 'tasks', community_id=ids['communities'], created_by_id=ids['users'], impact_point_reward=20, title='Staging video', priority='NORMAL', task_type='video')
        insert(connection, 'task_assignments', task_id=ids['tasks'], assignee_id=ids['users'], assigned_by_id=ids['users'], status='VERIFIED')
        insert(connection, 'task_submissions', assignment_id=ids['task_assignments'], evidence_text='Real staging evidence')
        insert(connection, 'impact_transactions', user_id=ids['users'], community_id=ids['communities'], task_id=ids['tasks'], source_type='task_completion', source_id=ids['task_assignments'], points=5, status='POSTED', idempotency_key='historical-task-award')
        insert(connection, 'point_rules', source_type='task_completion', points=5)
        insert(connection, 'point_rules', source_type='task_completion', points=10)
    engine.dispose()
    command.upgrade(config, 'head')
    engine = sa.create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(sa.text('SELECT reward_mode, impact_point_reward FROM tasks')).one() == ('legacy_rule', 20)
        assert connection.execute(sa.text('SELECT evidence_text FROM task_submissions')).scalar_one() == 'Real staging evidence'
        assert connection.execute(sa.text('SELECT points FROM impact_transactions')).scalar_one() == 5
        assert connection.execute(sa.text('SELECT maximum_points FROM point_ceilings')).scalar_one() == 10
        assert connection.execute(sa.text('SELECT COUNT(*) FROM point_rules')).scalar_one() == 2
        assert connection.execute(sa.text('SELECT COUNT(*) FROM point_rules WHERE is_active = 1')).scalar_one() == 1
    indexes = sa.inspect(engine).get_indexes('point_rules')
    assert any(i['name'] == 'uq_active_global_point_rule' and i['unique'] for i in indexes)
    engine.dispose()
    command.downgrade(config, 'b7c8d9e0f123')
    command.upgrade(config, 'head')


def test_postgresql_migration_compiles_without_connection(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(settings, 'database_url', 'postgresql://migration-test/unused')
    command.upgrade(Config('alembic.ini', output_buffer=output), 'b7c8d9e0f123:c8d9e0f12345', sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE point_ceilings' in sql
    assert 'INSERT INTO point_ceilings' in sql
    assert 'uq_active_global_point_rule' in sql
    assert 'DROP TABLE' not in sql and 'DELETE FROM' not in sql
