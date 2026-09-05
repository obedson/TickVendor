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

### Render/Brevo registration verification procedure

Use the Render staging API service and the Brevo SMTP relay. Never put the SMTP password in Git, tickets, screenshots, or chat.

1. In Brevo, verify the sender identity used by staging and create or select an SMTP key. Use the Brevo SMTP host shown for the account (commonly `smtp-relay.brevo.com`), port `2525` for the Render Free Web Service network path, the Brevo SMTP login, the SMTP key as `SMTP_PASSWORD`, and the verified sender as `SMTP_FROM_ADDRESS`. Port 587 was unable to connect from the observed Render Free service; 2525 is the externally verified staging setting.
2. In the Render API service Environment settings, set `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT=2525`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_ADDRESS`. Keep staging PostgreSQL, Redis, S3, `DEBUG=false`, and strict CORS unchanged. Save and deploy; confirm migrations complete before Uvicorn starts and credentials are absent from logs.
3. From `https://tickvendor-1.onrender.com`, register a unique controlled test address. Confirm HTTP 201, provider acceptance in Brevo, and Gmail/mailbox receipt. The observed evidence is successful Render → Brevo → Gmail delivery from `noreply@solafeed.com` using port 2525. SMTP acceptance alone does not verify the account.
4. Confirm the email contains a user-facing `Verify your email address` link/button pointing to the configured `FRONTEND_URL` `/verify-email?token=...`; it must not present the raw token as the action. Click it and confirm the frontend success state, HTTP 204, and persisted `email_verified_at`.
5. For a separate account, exercise a controlled SMTP timeout/failure in staging. Confirm HTTP 503, CORS `access-control-allow-origin: https://tickvendor-1.onrender.com`, and no user/profile/session/auth-token residue in PostgreSQL. Restore valid Brevo settings and redeploy.
6. Register the same email after recovery and confirm HTTP 201; repeat it and confirm HTTP 409. Use `Resend verification email` for an active unverified account and confirm HTTP 202, a new message, and unchanged unverified state until token verification.
7. For verified, inactive, or nonexistent addresses, confirm generic HTTP 202 with no message. Resend must never mark an account verified.

The remaining external question is SMTP connectivity and mailbox/provider receipt in Render staging. Local tests prove rollback, controlled errors, CORS, resend state safety, and recovery, not Brevo acceptance or mailbox receipt.

## PostgreSQL and workers

Run Alembic from an empty PostgreSQL database. Start at least two worker processes and submit the same scheduled work and idempotent reward concurrently. Verify one claim, no duplicate side effects, durable retry/backoff, and terminal failure after the configured attempt limit. Repeat after a provider-accepted-before-process-crash simulation and document the resulting delivery boundary.

## Distributed rate limiting

Configure the production shared limiter (for example Redis or an equivalent managed service), run requests through multiple application instances, and verify limits are shared across instances, reset behavior, trusted proxy handling, and fail-closed/fail-open policy.

## Object storage, HTTPS, operations

Configure production object storage credentials and private/public bucket policy. Verify upload MIME/magic-byte/size validation, object authorization, deletion/retention, and URL delivery. Deploy behind HTTPS for `tickvendor.com` and `www.tickvendor.com`, verify CORS/security headers, health checks, error tracking, API latency, webhook/attendance/auth failure alerts, encrypted backups, restore to an isolated database, migration rollback, and load behavior on mobile/low-bandwidth profiles.
