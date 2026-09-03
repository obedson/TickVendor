# TickVendor external verification runbook

This runbook lists required evidence that cannot be established by local SQLite, in-memory adapters, or browser tests.

## Paystack

1. Set `ENVIRONMENT=staging`, a strong `SECRET_KEY`, `DATABASE_URL` to PostgreSQL, `PAYMENT_PROVIDER=paystack`, `PAYSTACK_SECRET_KEY`, and `PAYSTACK_WEBHOOK_SECRET` from the secret manager.
2. Configure Paystack sandbox webhook delivery to `/api/v1/payments/webhooks/paystack`.
3. Execute free, successful paid, declined, mismatched amount/currency, duplicate reference, duplicate webhook, and timeout cases.
4. Record provider reference, authoritative verification response, webhook response, final payment/order/ticket states, and audit records.
5. Exercise refund initiation and provider reconciliation only after those capabilities are implemented; do not treat local refund state mutation as provider confirmation.

## Email and push

Set `EMAIL_PROVIDER=smtp` with `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_ADDRESS`, or `PUSH_PROVIDER=http` with `PUSH_ENDPOINT` and `PUSH_API_TOKEN` in staging. Send a notification to a controlled test identity, verify provider acceptance and receipt, then test preference suppression, community-rule suppression, retry, and terminal failure. Never record credentials or message secrets in logs.

## PostgreSQL and workers

Run Alembic from an empty PostgreSQL database. Start at least two worker processes and submit the same scheduled work and idempotent reward concurrently. Verify one claim, no duplicate side effects, durable retry/backoff, and terminal failure after the configured attempt limit. Repeat after a provider-accepted-before-process-crash simulation and document the resulting delivery boundary.

## Distributed rate limiting

Configure the production shared limiter (for example Redis or an equivalent managed service), run requests through multiple application instances, and verify limits are shared across instances, reset behavior, trusted proxy handling, and fail-closed/fail-open policy.

## Object storage, HTTPS, operations

Configure production object storage credentials and private/public bucket policy. Verify upload MIME/magic-byte/size validation, object authorization, deletion/retention, and URL delivery. Deploy behind HTTPS for `tickvendor.com` and `www.tickvendor.com`, verify CORS/security headers, health checks, error tracking, API latency, webhook/attendance/auth failure alerts, encrypted backups, restore to an isolated database, migration rollback, and load behavior on mobile/low-bandwidth profiles.
