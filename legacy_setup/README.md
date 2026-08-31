# Legacy Setup Scripts

`setup_venv.py`, `install_pkgs.py`, and `install_remaining.py` are preserved only as recovery artifacts.
They are not supported installation entry points and must not be used by CI, deployment, or contributors.

Supported setup from the repository root:

    python -m venv venv
    ./venv/Scripts/python.exe -m pip install -e '.[dev]'
    ./venv/Scripts/alembic.exe upgrade head
    ./venv/Scripts/python.exe -m pytest -q

Runtime and development dependencies are declared in `pyproject.toml`.
