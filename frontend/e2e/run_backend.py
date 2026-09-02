"""Start an isolated API for Playwright tests."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / '.tmp-e2e.db'}"
os.environ["ENVIRONMENT"] = "test"
os.environ["PAYMENT_PROVIDER"] = "test"

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, log_level="warning")
