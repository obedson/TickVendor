"""Verify upgrade from deployed head in an isolated SQLite database."""
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from src.config import settings


def test_governance_migration_upgrades_current_head(tmp_path, monkeypatch):
    config = Config('alembic.ini')
    assert ScriptDirectory.from_config(config).get_heads() == ['b7c8d9e0f123']
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setattr(settings, 'database_url', url)
    command.upgrade(config, '9f0a1b2c3d4e')
    command.upgrade(config, 'head')
    engine = create_engine(url)
    inspector = inspect(engine)
    assert 'personal_archives' in inspector.get_table_names()
    assert 'membership_access' in {column['name'] for column in inspector.get_columns('communities')}
    for table in ['events','activity_opportunities','tasks']:
        assert 'is_suspended' in {column['name'] for column in inspector.get_columns(table)}
        assert f'ix_{table}_suspended' in {index['name'] for index in inspector.get_indexes(table)}
    assert 'ix_memberships_community_status' in {index['name'] for index in inspector.get_indexes('memberships')}
    assert 'uq_personal_archive_owner_item' in {constraint['name'] for constraint in inspector.get_unique_constraints('personal_archives')}
    assert 'ck_personal_archive_type' in {constraint['name'] for constraint in inspector.get_check_constraints('personal_archives')}
    with engine.connect() as connection:
        assert connection.execute(text('select version_num from alembic_version')).scalar() == 'b7c8d9e0f123'
    engine.dispose()
    command.downgrade(config, '9f0a1b2c3d4e')
    engine = create_engine(url)
    assert 'personal_archives' not in inspect(engine).get_table_names()
    engine.dispose()
    command.upgrade(config, 'head')


def test_governance_migration_postgresql_sql_compiles(monkeypatch):
    from io import StringIO

    output = StringIO()
    config = Config('alembic.ini', output_buffer=output)
    monkeypatch.setattr(settings, 'database_url', 'postgresql://migration-test/unused')
    command.upgrade(config, '9f0a1b2c3d4e:b7c8d9e0f123', sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE personal_archives' in sql
    assert 'UNIQUE (user_id, item_type, item_id)' in sql
    assert 'BOOLEAN DEFAULT false NOT NULL' in sql
    assert 'DROP TABLE' not in sql
