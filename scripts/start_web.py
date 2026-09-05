"""Run database migrations before replacing this process with the API server."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execvp(
        "uvicorn",
        ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "8000")],
    )


if __name__ == "__main__":
    main()
