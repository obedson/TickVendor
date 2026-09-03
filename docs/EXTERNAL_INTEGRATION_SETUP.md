# TickVendor external integration setup guide

This guide is repository-specific and was prepared from the current settings, adapters, migrations, Docker/Compose files, upload code, worker code, and README. It does not assume any account or credential already exists. Never send secret values in chat.

Readiness gate: object storage is not ready for credentials. The upload implementation is filesystem-only and must be replaced behind a storage abstraction before bucket provisioning. Direct native Web Push/FCM/APNs registration is also not implemented; the current push adapter is ready only for a gateway that accepts its generic HTTP contract.

## Readiness summary

| Subsystem | Status | Implementation ready? | Credentials required? | External service? | Owner action | Hermes action after ready |
|---|---|---:|---:|---:|---|---|
| PostgreSQL | READY FOR CREDENTIALS | Yes | Yes | Yes | Create staging DB and add `DATABASE_URL` to secret store | Fresh migration, suite, PostgreSQL transaction/concurrency checks |
| Paystack sandbox | READY FOR CREDENTIALS | Yes for checkout/verify/webhook; refunds/reconciliation are not implemented | Yes | Yes | Create/test account, obtain keys, configure webhook | Real sandbox checkout/webhook/failure/replay acceptance |
| Redis distributed limiter | READY FOR CREDENTIALS | Yes, opt-in `RedisRateLimiter` implementation | Yes | Yes | Provision TLS Redis and set `REDIS_URL`, enable flag | Multi-instance shared-limit test and failure-policy check |
| Object storage | LOCAL IMPLEMENTATION STILL REQUIRED | No: uploads currently write to local `TICKVENDOR_UPLOAD_DIR` filesystem | Yes eventually | Yes | Do not provision yet for acceptance | Implement S3-compatible storage abstraction first |
| SMTP email | READY FOR CREDENTIALS | Yes, `SMTPEmailSender` | Yes | Yes | Create SMTP/provider account and verified sender | Controlled receipt, suppression, retry, terminal-failure tests |
| Push | READY FOR CREDENTIALS for configured HTTP gateway | Adapter is generic HTTP, not native Web Push/FCM/APNs | Yes | Yes | Choose gateway exposing the required endpoint contract | Gateway acceptance and device receipt; native push gap review |
| Staging deployment | READY FOR CREDENTIALS | Basic Docker/Compose exists; no CI deploy/reverse proxy | Yes | Yes | Choose platform and provision services | Deploy, migrate, smoke test, worker and rollback rehearsal |
| Domain/DNS/HTTPS | EXTERNAL SETUP REQUIRED | App has canonical URL/CORS values; no DNS/TLS config in repo | DNS/certificate access | Yes | Configure staging first, production later | Verify TLS, CORS, headers, callback/webhook reachability |
| Monitoring | LOCAL IMPLEMENTATION PARTIAL | JSON logs, request IDs, redaction exist; external collection/alerts absent | Service DSN/API keys | Yes | Choose error/metrics service | Trigger and verify alerts |
| Backups/restore | EXTERNAL SETUP REQUIRED | No repository backup implementation | Provider backup access/keys | Yes | Enable managed backups and isolated restore target | Restore and RPO/RTO evidence |

## 1. Paystack

Repository facts:
- Provider selection is `PAYMENT_PROVIDER=paystack`.
- Checkout calls Paystack `POST https://api.paystack.co/transaction/initialize`.
- Amount is converted from major currency units to kobo-like minor units by multiplying by 100.
- Verification calls `GET https://api.paystack.co/transaction/verify/{provider_reference}`.
- Webhook route is `/api/v1/payments/webhooks/paystack`.
- The webhook reads `x-paystack-signature` and calculates HMAC-SHA512.
- TickVendor accepts a distinct `PAYSTACK_WEBHOOK_SECRET`; if it is empty, the adapter falls back to the Paystack API secret.
- The Paystack adapter does not use a separate callback URL during initialization. The frontend uses the returned `authorization_url`; the payment-return screen uses the local payment ID and then calls the authoritative status/verify APIs.
- The accepted Paystack event is `charge.success`. Other Paystack events are ignored.
- Currency is the order currency; the current V1 path and fixtures use `NGN`.

Owner setup:
1. Create or select a Paystack account and switch to Test Mode.
2. In Paystack Dashboard → Settings → API Keys & Webhooks, copy the Test Secret Key into the staging secret store as `PAYSTACK_SECRET_KEY`.
3. Decide the webhook signing secret. If Paystack provides/configures a distinct webhook secret for the account, put it in `PAYSTACK_WEBHOOK_SECRET`; otherwise use the same secret key only if that is the account's actual signing behavior. Do not paste either value into chat.
4. Configure webhook URL `https://api-staging.tickvendor.com/api/v1/payments/webhooks/paystack` (replace the hostname with the actual staging API hostname).
5. Enable delivery for `charge.success`.
6. Use a Paystack test card/transaction in Test Mode. Do not use production money.
7. Report: “Paystack sandbox credentials and webhook are configured in staging secrets; no keys sent in chat.” Include the staging API hostname and webhook delivery status, not the secret.

Acceptance sequence:
checkout → Paystack test page → returned authorization/callback URL → local payment status/verify → server-side Paystack verification → signed `charge.success` webhook → payment/order/ticket state → replay → failed/declined/mismatch cases.

Refund/reconciliation status:
- Local `refund_order` only changes local Payment/Order/Ticket state.
- No Paystack refund-initiation API call exists.
- No provider refund reconciliation job exists.
- Do not use external Paystack credentials for refund acceptance until those local capabilities are implemented.

## 2. PostgreSQL

Repository facts:
- SQLAlchemy accepts `DATABASE_URL` through Pydantic settings.
- Production/staging reject SQLite URLs.
- Compose uses PostgreSQL 17 and `postgresql+psycopg://...`.
- Alembic owns migrations.

Recommended staging option: use any managed PostgreSQL service that supplies a PostgreSQL 15+ or 17 instance, TLS, backups, connection details, and an isolated database. The repository does not select a cloud vendor, so Supabase, Neon, Render PostgreSQL, Railway PostgreSQL, or a managed cloud PostgreSQL are compatible; choose one with a private/staging database and TLS.

Owner setup:
1. Create a staging PostgreSQL instance/database.
2. Create a least-privilege application user and a separate migration-capable deployment user if the platform supports it.
3. Require TLS and copy the provider's connection URL into the staging secret store as `DATABASE_URL`, using `postgresql+psycopg://user:password@host:5432/database?sslmode=require` or the provider's equivalent accepted by psycopg.
4. Report only that the staging PostgreSQL URL is configured and the server version/host provider; do not send credentials.

Hermes verification:
- Run `DATABASE_URL=... alembic upgrade head` against an empty staging DB.
- Run `alembic current` and `alembic check`.
- Run backend tests against a disposable PostgreSQL database where possible.
- Run two worker/app processes with the same idempotency inputs and inspect one durable result.
- SQLite remains development/test only; it cannot prove PostgreSQL locking or multi-worker semantics.

## 3. Redis/distributed rate limiting

The repository now has `RedisRateLimiter` using `redis.Redis.from_url`, atomic `INCR`, one-second connection timeouts, and a fixed-window expiry. Enable it with:
- `REDIS_URL`
- `DISTRIBUTED_RATE_LIMIT_ENABLED=true`

Use `rediss://` for TLS, for example `rediss://:<password>@host:6380/0`. The current failure behavior is a provider exception from the limiter; production must decide whether the edge/proxy fails closed or whether a health-controlled fallback is acceptable before enabling it.

Owner setup:
1. Provision a TLS Redis-compatible shared store.
2. Create a restricted application credential.
3. Set the two variables in staging secrets.
4. Report the store is reachable/configured without sending the URL or password.

Hermes will run two app instances, send the same endpoint traffic across both, verify one shared quota and expiry, test Redis outage behavior, and inspect that secrets are not logged.

## 4. Object storage

Current status: LOCAL IMPLEMENTATION STILL REQUIRED.

The upload path in `src/api/events.py` writes validated bytes to `Path(os.environ.get("TICKVENDOR_UPLOAD_DIR", "uploads")) / "events"`. There is no S3/object-storage abstraction, no storage settings model, no signed URL path, and no storage deletion/retention service. Do not provision a production bucket as if this feature were ready. Hermes must implement and test the abstraction before real object-storage verification.

Current local restrictions already enforced: JPEG/PNG/WebP MIME and magic-byte validation, WebP container validation, and 5 MB maximum. A future storage integration must preserve those rules, tenant/owner authorization, safe object names, and explicit private/public delivery policy.

Hermes will implement this before requesting bucket credentials. The owner should provision no production bucket for TickVendor acceptance yet.

## 5. SMTP email

Variables expected by the current adapter:
- `EMAIL_PROVIDER=smtp`
- `SMTP_HOST`
- `SMTP_PORT` (normally 587)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_ADDRESS`

The adapter uses STARTTLS, a 10-second timeout, optional username/password login, and no credential logging. The owner must create an SMTP account or provider API-to-SMTP credential, verify the sender/from address, and nominate a controlled staging mailbox. App passwords are preferred where the provider supports them.

Hermes will send a controlled notification, verify the provider's acceptance response and the mailbox receipt with the owner, then test participant opt-out, community suppression, retryable failure, terminal failure, and no-secret logging. Live mailbox receipt remains unverified until this is done.

## 6. Push notifications

Variables expected:
- `PUSH_PROVIDER=http`
- `PUSH_ENDPOINT`
- `PUSH_API_TOKEN`

The current adapter sends an HTTP POST with JSON:
`{"user_id":"<UUID>","title":"...","body":"...","data":{...}}`
with an optional `Authorization: Bearer <PUSH_API_TOKEN>` header and a 10-second timeout.

This is a generic gateway adapter. It is not itself Web Push, FCM, or APNs: it does not store browser subscription objects, device tokens, VAPID keys, FCM registration tokens, or APNs device tokens. The selected gateway must resolve `user_id` to a registered device/subscription and return a non-error HTTP response. If the intended product requirement is direct browser/mobile push, Hermes must add a native Web Push/FCM/APNs registration and delivery implementation before claiming that capability is ready.

## 7. Deployment/platform

Repository artifacts:
- Dockerfile builds only the backend and starts Uvicorn.
- Compose defines API, PostgreSQL 17, and Redis 7 with persistent volumes.
- GitHub Actions runs quality tests and Gitleaks; it does not deploy.
- No reverse-proxy, frontend-hosting, worker service, IaC, or cloud secret-manager configuration exists.

Simplest compatible staging choices:
1. Recommended: Render/Fly/Railway-style managed deployment with one backend service, one worker service, managed PostgreSQL, managed Redis, and static frontend hosting.
2. Docker Compose on a small VPS with PostgreSQL/Redis volumes and a reverse proxy.
3. Any managed container platform with separate API and worker processes plus managed database services.

Owner chooses the platform, creates the project/account, provisions services, and gives Hermes the non-secret service URLs. Hermes can update deployment files/runbooks, migrations, health checks, worker commands, and smoke tests, but cannot create provider accounts or authorize deployments without owner access.

The Compose API container currently starts Uvicorn only; it does not run Alembic automatically. Run migrations as a release/deploy step before starting or exposing the API. The worker entrypoint is `./venv/Scripts/python.exe scripts/notification_worker.py` (or `python scripts/notification_worker.py` in the container) and should run as a separate staging/production process.

## 8. Domain/DNS/HTTPS

Safe staging convention:
- Frontend: `https://staging.tickvendor.com`
- API/webhooks: `https://api-staging.tickvendor.com`

Owner later configures:
- Apex `tickvendor.com` to frontend hosting.
- `www.tickvendor.com` as a canonical redirect to the apex or the chosen canonical host.
- API hostname as a separate HTTPS record.
- TLS certificates through the hosting platform or ACME.
- CORS to the actual frontend origin only.
- Paystack webhook to the HTTPS API hostname.

Do not change production DNS now. Current settings already contain `https://tickvendor.com` and `https://www.tickvendor.com` in default CORS/canonical configuration, but no DNS or TLS deployment exists. Hermes will verify HTTPS, redirects, CORS, security headers, callback reachability, webhook reachability, and PWA behavior after staging is live.

## 9. Monitoring and alerting

Already implemented locally:
- JSON application logs.
- Request correlation IDs and `X-Request-ID`.
- Secret redaction in logs/audit metadata.
- Generic safe 500 envelope.
- Health endpoint `/health`.
- Audit records for sensitive domain changes.

Missing external setup:
- Error-tracking collector/DSN.
- Frontend error tracking.
- API latency/metrics collector.
- Payment webhook failure alerts.
- Authentication failure alerts.
- Attendance failure/abuse signal alerts.
- Notification worker failure alerts.
- Database health/connection monitoring.
- Deployment health alerts.

No repository variables currently exist for monitoring; do not invent them as application settings until Hermes adds the integration. Owner chooses the monitoring service and creates its DSN/API credentials. Hermes can add structured metrics/error hooks once the service and desired protocol are selected.

## 10. Backups and restore

Use managed PostgreSQL automated backups plus an independent encrypted backup/export if the provider supports it. Owner configures retention and backup credentials in the provider secret manager. Hermes will provide/execute a staging procedure: create backup, restore to an isolated database, run migrations/checks, compare representative row counts/checksums, and record RPO/RTO. Never test restore by overwriting the live database.

## 11. Staging environment checklist

Use `.env.staging.example` as the placeholder template. It includes core, PostgreSQL, Paystack, SMTP, push, Redis, storage placeholders, frontend/API, CORS, monitoring, and worker sections. Storage variables are intentionally placeholders only because the local object-storage implementation is not yet ready. The currently consumed application variables are:

- Core: `APP_NAME`, `ENVIRONMENT`, `DEBUG`, `API_V1_PREFIX`, `CANONICAL_URL`, `LOG_LEVEL`, `SECRET_KEY`, token expiry values, bcrypt rounds.
- Database: `DATABASE_URL`.
- Paystack: `PAYMENT_PROVIDER`, `PAYSTACK_SECRET_KEY`, `PAYSTACK_WEBHOOK_SECRET`.
- SMTP: `EMAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS`.
- Push: `PUSH_PROVIDER`, `PUSH_ENDPOINT`, `PUSH_API_TOKEN`.
- Redis: `REDIS_URL`, `DISTRIBUTED_RATE_LIMIT_ENABLED`.
- CORS: `CORS_ORIGINS`.

The `STORAGE_*`, `FRONTEND_URL`, `API_URL`, monitoring, and worker variables in the example are preparation placeholders, not currently consumed by application code. Hermes must wire any of them before they are used as acceptance evidence.

## 12. Secret handling

Secrets:
- `SECRET_KEY`
- `PAYSTACK_SECRET_KEY`
- `PAYSTACK_WEBHOOK_SECRET`
- `FLUTTERWAVE_SECRET_KEY`
- `FLUTTERWAVE_WEBHOOK_SECRET`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SMTP_PASSWORD`
- `PUSH_API_TOKEN`
- PostgreSQL/Redis/storage credentials when provisioned
- Monitoring DSN/API tokens when provisioned

Safe configuration includes provider names, ports, API prefixes, non-secret URLs, `ENVIRONMENT`, CORS origins, and feature flags. Local development uses an ignored `.env`; staging/production uses the deployment platform's secret manager/environment secrets. `.gitignore` ignores `.env` and `.env.*` while allowing `.env.example`; the staging example contains placeholders only.

## Recommended order

1. Owner selects a staging platform and provisions PostgreSQL.
2. Owner adds strong staging core secrets and PostgreSQL URL.
3. Hermes migrates a fresh staging DB and runs backend verification.
4. Hermes completes the object-storage abstraction before bucket provisioning.
5. Owner provisions Redis and enables the distributed limiter; Hermes runs multi-instance verification.
6. Hermes must replace the filesystem upload path with a storage abstraction before the owner provisions an object-storage bucket.
7. Owner deploys API, worker, and frontend to staging.
8. Owner creates Paystack Test Mode keys and webhook; Hermes runs checkout/webhook acceptance.
9. Owner configures SMTP; Hermes verifies provider acceptance and controlled mailbox receipt.
10. Decide whether the generic push gateway is sufficient or whether direct Web Push/FCM/APNs is required; provision only after that decision.
11. Owner enables backups and provides an isolated restore target; Hermes runs restore evidence.
12. Owner configures monitoring/alerting; Hermes triggers controlled failures.
13. Owner configures staging DNS/TLS; Hermes runs HTTPS/CORS/webhook/PWA checks.
14. Run full staging acceptance and only then plan production domain/provider rollout.

# WHAT OBEDSON NEEDS TO DO

1. Choose a staging platform and create the project.
   - Provision a managed PostgreSQL database with TLS and a managed Redis-compatible store if the chosen platform does not provide Compose services.
   - Report the platform name, staging frontend URL, staging API URL, PostgreSQL server version, and whether Redis is TLS-enabled. Do not send credentials.

2. Add staging core secrets.
   - Add a generated strong `SECRET_KEY` and the staging `DATABASE_URL` to the platform secret manager.
   - Keep `ENVIRONMENT=staging` and `DEBUG=false`.
   - Report: “Staging core secrets are configured.”

3. Configure the staging deployment.
   - Deploy the backend, worker process, and frontend using the repository artifacts.
   - Report deployment URLs and service health, not secret values.

4. Paystack Test Mode.
   - Add `PAYSTACK_SECRET_KEY` and `PAYSTACK_WEBHOOK_SECRET` to staging secrets.
   - Configure `https://<staging-api-host>/api/v1/payments/webhooks/paystack` for `charge.success`.
   - Report: “Paystack sandbox configuration is ready.” Never send keys in chat.

5. SMTP provider.
   - Create/authorize SMTP credentials, verify the sender address, and add `EMAIL_PROVIDER=smtp`, SMTP host/port/user/password/from to staging secrets.
   - Choose a controlled mailbox for receipt verification.
   - Report: “SMTP staging configuration is ready,” plus the controlled recipient address only.

6. Push gateway decision.
   - Choose a gateway that accepts the current generic HTTP payload, or tell Hermes that direct Web Push/FCM/APNs is required.
   - If using the current adapter, add `PUSH_PROVIDER=http`, `PUSH_ENDPOINT`, and `PUSH_API_TOKEN` to staging secrets.
   - Report which path was chosen and the controlled device/subscription identity without sending the token.

7. Redis distributed limiter.
   - Add `REDIS_URL` and `DISTRIBUTED_RATE_LIMIT_ENABLED=true` after Redis TLS connectivity is ready.
   - Report: “Shared Redis limiter is ready.” Do not send the URL/password.

8. Object storage decision.
   - Do not provision a production bucket yet; the repository storage abstraction is not ready.
   - Report whether you want an S3-compatible provider and its non-secret endpoint/region choice so Hermes can implement the local abstraction.

9. Monitoring.
   - Choose an error/metrics service and create staging projects/alert channels.
   - Provide only the service name and non-secret endpoint/DSN placement instructions; store DSNs/tokens in the platform secret manager.

10. Backups.
    - Enable managed PostgreSQL backups, retention, encryption, and an isolated restore target.
    - Report backup frequency/retention and the isolated restore target availability.

11. Staging DNS/TLS.
    - Configure `staging.tickvendor.com` and `api-staging.tickvendor.com` only after services are healthy.
    - Report DNS/TLS readiness; do not modify production DNS yet.

# WHAT HERMES WILL DO AFTER EACH INTEGRATION IS READY

- PostgreSQL ready: run fresh Alembic upgrade/current/check, backend suite against staging/disposable PostgreSQL, transaction/idempotency checks, and concurrent worker/app verification.
- Paystack ready: run real sandbox initialize → hosted checkout → callback/status → authoritative verify → signed webhook → state readback → replay/mismatch/failure tests. Refund/reconciliation will remain blocked until local implementation exists.
- SMTP ready: send controlled staging notification, verify provider acceptance and mailbox receipt with the owner, then test preferences, community suppression, retry, terminal failure, and redaction.
- Push ready: exercise the configured gateway payload and authorization, verify provider acceptance/device receipt with the owner, then test suppression/retry. If native push is required, implement subscription/token support first.
- Redis ready: run two application instances, verify shared quota/reset, inspect timeout/failure behavior, and confirm no secret logging.
- Object storage ready after local implementation: run MIME/magic/size validation, authorized upload/read/delete, signed/private delivery if implemented, tenant isolation, retention, and cleanup tests.
- Deployment ready: deploy clean artifacts, run health checks, migrate a fresh DB, start API/worker/frontend, execute focused and full staging smoke suites, and rehearse rollback in isolation.
- DNS/HTTPS ready: verify apex/www/staging redirects, certificates, CORS, CSP/security headers, Paystack webhook reachability, callback reachability, and PWA installation.
- Monitoring ready: trigger controlled auth, webhook, attendance, worker, database, and latency failures; verify alerts and redaction.
- Backups ready: create backup, restore to isolated DB, compare schema/data evidence, and record RPO/RTO.

Exact message after the first setup step:

“Staging platform and PostgreSQL are provisioned. The staging `DATABASE_URL` and strong `SECRET_KEY` are stored in the platform secret manager; no secrets are included here. Staging API URL: <non-secret URL>. Staging frontend URL: <non-secret URL>.”
