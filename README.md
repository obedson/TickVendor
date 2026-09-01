# TickVendor

TickVendor combines events, ticketing, verified attendance, community activity, and configurable recognition.

Local backend setup:

    python -m venv venv
    ./venv/Scripts/python.exe -m pip install -e '.[dev]'
    ./venv/Scripts/alembic.exe upgrade head
    ./venv/Scripts/python.exe -m pytest -q
    ./venv/Scripts/python.exe -m uvicorn src.main:app --reload

Frontend:

    cd frontend
    npm install
    npm run build
    npm run dev

Configuration is documented in `.env.example`. SQLite is allowed only for development/test. Staging and production require a server database URL and strong `SECRET_KEY`. Apply Alembic migrations before startup.

Live payment provider and production email delivery require external credentials; deterministic adapters cover local development and tests.
