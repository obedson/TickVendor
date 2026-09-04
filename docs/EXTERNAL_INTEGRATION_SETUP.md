# TickVendor external integration readiness

This repository is locally ready for credential-backed staging verification. Secrets belong in the deployment platform secret store, never Git or chat.

Paystack
- `x-paystack-signature` is HMAC-SHA512 of the raw request body using `PAYSTACK_SECRET_KEY` by default.
- `PAYSTACK_WEBHOOK_SECRET` is only an optional internal override; Paystack does not issue a separate signing credential.
- Initialization supplies `${FRONTEND_URL}/payment/return`. The return page reads only TickVendor's local `payment_id` and polls the authenticated backend record; provider query parameters never prove success.
- Refund initiation calls Paystack `POST /refund`. Local payment/order/ticket status changes only after provider status is `success`; pending initiation is stored safely for replay.
- Reconciliation compares provider reference, amount, currency, and status, records an audit event, and never silently corrects a mismatch.

Object storage
- `STORAGE_PROVIDER=local` is retained for development/test.
- Staging/production require `STORAGE_PROVIDER=s3` and a private S3-compatible bucket.
- Objects use tenant/event-aware keys under `communities/<community>/events/<event>/cover/`.
- Existing 5 MB, MIME, and magic-byte validation remains before storage.
- Private reads use bounded pre-signed URLs; no public ACL is set. Delete support exists for retention/lifecycle integration.

Push
- The specification requires push notifications but does not mandate Web Push, FCM, or APNs.
- TickVendor therefore uses a generic HTTPS gateway contract: `POST PUSH_ENDPOINT` with `user_id`, `title`, `body`, and `data`, plus optional bearer authentication.
- The gateway owns subscription/device-token resolution. Direct browser/mobile subscription management is not claimed.

Monitoring
- Structured request latency, exception, payment failure, and worker failure events can be sent to a vendor-neutral HTTP collector through `METRICS_ENDPOINT` and `MONITORING_API_TOKEN`.
- Correlation IDs are included. Exception messages and secrets are not placed in monitoring payloads.
- `/health` verifies database connectivity and acts as deployment/database health signal.

Redis
- Local development may disable distributed limiting and uses the in-process limiter.
- Staging/production must enable Redis and provide `REDIS_URL`; configuration otherwise fails at startup.
- Redis timeout/unavailability fails closed with HTTP 503 rather than silently removing limits.

Deployment
- Release migration command: `alembic upgrade head`.
- Compose runs migrations before the API; managed platforms should use the same release command.
- API command: `uvicorn src.main:app --host 0.0.0.0 --port 8000`.
- Worker command: `python scripts/notification_worker.py`.
- Frontend build consumes infrastructure variable `VITE_API_ORIGIN`.
- Staging/production reject SQLite, local object storage, missing Redis distributed limiting, insecure canonical/frontend URLs, and missing Paystack credentials.

Credential checklist

| System | Variables | Account/credential |
|---|---|---|
| PostgreSQL | `DATABASE_URL` | TLS PostgreSQL application URL |
| Redis | `REDIS_URL`, `DISTRIBUTED_RATE_LIMIT_ENABLED` | TLS Redis URL/credential |
| Object storage | `STORAGE_PROVIDER`, `STORAGE_BUCKET`, `STORAGE_REGION`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_SIGNED_URL_TTL_SECONDS` | Private S3-compatible bucket and least-privilege key |
| Paystack | `PAYMENT_PROVIDER`, `PAYSTACK_SECRET_KEY`, optional `PAYSTACK_WEBHOOK_SECRET` | Paystack Test Secret Key; no separate Paystack webhook secret |
| SMTP | `EMAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS` | SMTP credential and verified sender |
| Push | `PUSH_PROVIDER`, `PUSH_ENDPOINT`, `PUSH_API_TOKEN` | Generic gateway endpoint/token |
| Monitoring | `METRICS_ENDPOINT`, `MONITORING_API_TOKEN` | Structured-event collector endpoint/token |
| Frontend/CORS | `FRONTEND_URL`, `CANONICAL_URL`, `CORS_ORIGINS`, `VITE_API_ORIGIN` | Non-secret HTTPS deployment origins |
| Core | `SECRET_KEY`, `ENVIRONMENT`, `DEBUG` | Random application signing secret |

Staging acceptance remains external: provider delivery, multi-instance behavior, private object retrieval, Paystack sandbox checkout/refund/reconciliation, SMTP receipt, push device receipt, alert delivery, DNS/TLS, and restore evidence.

CORS configuration: `CORS_ORIGINS` is parsed by the application as either a JSON array or a comma-separated string. In Render, use the exact JSON value `[
  "https://tickvendor-1.onrender.com"
]` (single line: `["https://tickvendor-1.onrender.com"]`). The JSON form is recommended for an unambiguous single origin. Origins are normalized by removing surrounding whitespace and a trailing slash; wildcard `*` is not accepted as a substitute for the allowlist.
