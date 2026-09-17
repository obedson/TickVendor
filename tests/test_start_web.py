"""Deployment entrypoint command contract."""
import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_start_web_runs_alembic_before_uvicorn():
    source = Path("scripts/start_web.py").read_text()
    assert '"-m", "alembic", "upgrade", "head"' in source
    assert "os.execvp" in source
    assert source.index("subprocess.run") < source.index("os.execvp")


def test_blank_database_migrates_to_current_head(tmp_path):
    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert len(heads) == 1, f"expected a single migration head, found {heads}"
    database = tmp_path / "blank.db"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=environment, capture_output=True, text=True, check=True,
    )
    assert "initial schema" in result.stdout + result.stderr
    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        env=environment, capture_output=True, text=True, check=True,
    )
    assert f"{heads[0]} (head)" in current.stdout + current.stderr
