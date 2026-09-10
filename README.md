# TickVendor Architecture and Operations

## Architecture

TickVendor is a FastAPI/SQLAlchemy backend under `src/`, a Vite/React frontend under `frontend/`, and Alembic migrations under `migrations/`. The backend is authoritative for authentication, authorization, tenant scope, ticket/payment state, attendance, tasks, contributions, Impact Points, recognition, notifications, and audit records. The frontend uses bearer sessions and lazy-loaded role-specific screens.

## Local setup

    python -m venv venv
    ./venv/Scripts/python.exe -m pip install -e '.[dev]'
    ./venv/Scripts/alembic.exe upgrade head
    ./venv/Scripts/python.exe scripts/seed_demo.py
    ./venv/Scripts/python.exe -m pytest -q
    cd frontend && npm install && npm run lint && npm run build

Run the API with `./venv/Scripts/python.exe -m uvicorn src.main:app --reload`. Run the frontend with `cd frontend && npm run dev`.

## Database, seeds, and first platform administrator

SQLite is for development/test only. Staging and production require a server database URL. Apply migrations before startup. The application seed module (`src/seed.py`) provides idempotent business configuration; the isolated browser fixture is `frontend/e2e/seed_e2e.py` and is never production data.

The development/demo seed creates demo accounts, including a Super Administrator, but must never be run against staging or production. To provision the first real platform Super Administrator, first register and email-verify the operator account through the normal authentication flow, then run this one-time command from a trusted deployment shell with `DATABASE_URL` set to the intended database:

    ./venv/Scripts/python.exe scripts/provision_first_super_admin.py --email operator@example.com --confirm

The command refuses to run if a Super Administrator already exists, if the account is inactive or unverified, or if confirmation is omitted. It promotes only that existing account and writes an append-only `platform.super_admin_bootstrapped` audit entry. It does not expose a public promotion endpoint and does not create credentials.

Default event categories are development/business seed data, not an application-startup side effect. After signing in to the provisioned Platform Admin account, use Platform Admin → Event Categories to create and activate the categories required by the deployment. Category mutations are backend-authorized for `super_admin` only.

## API and authentication

The REST API is prefixed `/api/v1`. Login returns bearer access/refresh tokens; send `Authorization: Bearer <access-token>`. Community resources enforce active membership and role server-side. Sensitive operations are audited. OpenAPI is available at `/docs` while the API is running.

## Payments

Paystack is the required payment provider. Configure `PAYSTACK_SECRET_KEY` and `PAYSTACK_WEBHOOK_SECRET`, then configure Paystack `charge.success` delivery to `/api/v1/payments/webhooks/paystack`. Verification is server-side and checks reference, amount, currency, and status. Local deterministic adapters/tests do not replace a Paystack sandbox or production acceptance run. Refund provider initiation and reconciliation still require implementation/verification work.

## Notifications

In-app notifications and participant preferences are available through `/api/v1/notifications`. Community notification rules are administered through `/api/v1/admin/communities/{community_id}/notification-rules`. Active community channel rules intersect with participant preferences. Scheduled work is claimed and delivered by the notification worker with retry/backoff and terminal failure state. SMTP and HTTP push adapters are selected by environment settings; live provider delivery remains unverified.

## Geolocation and recognition

Attendance requests location only after an explicit user action. QR and organizer fallback paths are available. Recognition definitions are database-backed and tenant-scoped; verified task, attendance, activity, and contribution transitions invoke the recognition engine. Awards use stable idempotency keys.

## PWA/offline

The frontend includes a manifest and service worker. The ticket wallet is encrypted in device-local storage and cleared on sign-out. Non-sensitive notification-read actions are queued for reconnect. Authenticated/private API responses are excluded from shared service-worker caching.

## Deployment and operations

Use a strong `SECRET_KEY`, server database, restricted CORS origins, `ENVIRONMENT=staging` or `production`, and `DEBUG=false`. Configure HTTPS/TLS, reverse proxy security headers, monitoring, alerting, backups, restore tests, and distributed rate limiting before production. Dockerfile provides a basic container entrypoint; no staging/production deployment is claimed by local tests.

## Validation

Backend: `./venv/Scripts/python.exe -m pytest -q`, `./venv/Scripts/ruff.exe check src tests migrations`, and a fresh Alembic upgrade/current/check. Frontend: `npm run lint`, `npm run build`, `npm run test:e2e`, plus the scripts under `frontend/scripts/` for responsive, offline, retry, PWA, payment-return, and bundle policy checks.

Detailed current requirement evidence is in `docs/TRACEABILITY_MATRIX.md`.
External staging/production verification steps are in `docs/EXTERNAL_VERIFICATION_RUNBOOK.md`.
The exact remaining-B verification manifest is in `docs/EXTERNAL_VERIFICATION_MANIFEST.md`.
External account and staging setup instructions are in `docs/EXTERNAL_INTEGRATION_SETUP.md`.
Run the scheduled notification worker separately with `./venv/Scripts/python.exe scripts/notification_worker.py` after migrations are applied.
Object storage remains filesystem-only until its production storage abstraction is implemented; the generic HTTP push adapter is not native Web Push/FCM/APNs.
