"""An in-process Alembic run must not silence the host application's loggers."""
import logging

from alembic import command
from alembic.config import Config

from src.config import settings


def test_in_process_migration_keeps_application_loggers_enabled(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration-logging.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    command.upgrade(Config("alembic.ini"), "head")
    logger = logging.getLogger("tickvendor.monitoring")
    assert not logger.disabled, "an in-process migration disabled the application monitoring logger"
    # The same symptom the payment test shows: a record must still reach a root handler.
    messages: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda record: messages.append(record.getMessage())
    root = logging.getLogger()
    previous_level = logger.level
    root.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info({"event": "migration_logging_probe"})
    finally:
        logger.setLevel(previous_level)
        root.removeHandler(handler)
    assert "migration_logging_probe" in " ".join(messages)
    assert logging.getLogger("alembic").getEffectiveLevel() == logging.INFO
