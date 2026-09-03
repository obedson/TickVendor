# TickVendor external verification manifest

The remaining 132 B rows in `docs/TRACEABILITY_MATRIX.md` classify as L1=73, L2=48, E1=2, E2=9. The current local pass exhausted L1/L2 evidence that could be safely established without inventing coverage; remaining B rows are retained where requirement-specific or external/deployed evidence is still incomplete.

## 1. PostgreSQL/database
- IDs: all B rows whose requirement text names PostgreSQL, database concurrency, transaction semantics, or migration behavior.
- Infrastructure: managed PostgreSQL and an isolated migration database.
- Configuration: `DATABASE_URL`, deployment secret, migration release process.
- Procedure: fresh base-to-head upgrade, concurrent idempotency/reward/worker tests, rollback rehearsal; retain logs and resulting row counts.
- Staging: yes. Destructive: rollback rehearsal can alter schema; use an isolated database and backup.

## 2. Paystack
- IDs: B rows mentioning real Paystack, sandbox/production checkout, webhook delivery, provider failure, refund, or reconciliation.
- Infrastructure/account: Paystack sandbox account and webhook endpoint.
- Configuration: `PAYMENT_PROVIDER=paystack`, `PAYSTACK_SECRET_KEY`, `PAYSTACK_WEBHOOK_SECRET`.
- Procedure: successful/declined/mismatched/replayed checkout, signed webhook, refund/reconciliation cases; retain provider references and local state/audit evidence.
- Staging: sandbox yes. Destructive: refunds may be irreversible; sandbox first.

## 3. Email
- IDs: B rows requiring live email/provider delivery.
- Account: SMTP/provider account and controlled mailbox.
- Configuration: `EMAIL_PROVIDER=smtp`, SMTP host/port/user/password/from.
- Procedure: send notification, verify provider acceptance and receipt, then suppression/retry/terminal-failure behavior.
- Staging: yes. Destructive: no.

## 4. Push
- IDs: B rows requiring live push/device delivery.
- Account: push gateway and controlled test device/token.
- Configuration: `PUSH_PROVIDER=http`, endpoint, API token.
- Procedure: send controlled push, verify gateway acceptance/device receipt, suppression and retry behavior.
- Staging: yes. Destructive: no.

## 5. Distributed rate limiting
- IDs: B rows requiring shared/horizontally scaled rate limiting.
- Infrastructure: Redis or equivalent shared limiter plus multiple app instances.
- Configuration: shared limiter URL/credentials and trusted proxy settings.
- Procedure: distribute requests across instances and verify one shared quota, reset, and failure policy.
- Staging: yes. Destructive: no.

## 6. Object storage
- IDs: B rows requiring production object storage/upload delivery.
- Infrastructure: S3-compatible bucket and access policy.
- Configuration: endpoint, bucket, credentials, private/public policy.
- Procedure: valid/invalid upload, authorization, URL delivery, retention and cleanup.
- Staging: yes. Destructive: cleanup uploaded objects only.

## 7. Staging/deployment
- IDs: B rows concerning staging/production deployment, secure environment, health checks, or release process.
- Infrastructure: CI/CD, container registry, staging host, reverse proxy.
- Configuration: staging secrets, server database, migration command, health endpoint.
- Procedure: deploy a clean artifact, run smoke/E2E and migration checks, capture release and rollback evidence.
- Staging: this is the staging procedure. Destructive: rollback is controlled; use isolated data.

## 8. Domain/DNS/HTTPS
- IDs: B rows concerning HTTPS/TLS, canonical domains, DNS, CORS, CSP/security headers, or PWA domain behavior.
- Infrastructure: DNS and certificate control for `tickvendor.com` and `www.tickvendor.com`.
- Configuration: certificates, DNS records, CORS allowlist, security headers.
- Procedure: verify both domains, TLS, redirect, CORS, CSP/security headers, and install behavior.
- Staging: preflight on staging; final domain requires production. Destructive: no.

## 9. Monitoring/alerting
- IDs: B rows concerning deployed error tracking, API performance, webhook, attendance, or authentication monitoring.
- Infrastructure: monitoring/error-tracking service and alert channel.
- Configuration: DSN/API keys, alert thresholds.
- Procedure: trigger representative failures and latency, verify alerts and redaction.
- Staging: yes. Destructive: no.

## 10. Backup/restore
- IDs: B rows concerning backup, restore, or disaster recovery.
- Infrastructure: encrypted backup store and isolated restore database.
- Configuration: backup credentials, encryption/retention policy.
- Procedure: backup, restore, compare row counts/checksums and measure RPO/RTO.
- Staging: yes. Destructive: restore target isolated.

## 11. Performance/load
- IDs: B rows concerning production-scale performance, low bandwidth, large datasets, or load.
- Infrastructure: load generator and production-like app/database.
- Configuration: representative large dataset and latency/error budgets.
- Procedure: test search, dashboards, ticketing, workers and mobile/low-bandwidth profiles; retain latency/resource evidence.
- Staging: yes. Destructive: no.

## 12. Production migrations/rollback
- IDs: B rows concerning production migration safety and rollback.
- Infrastructure: staging/prod-like PostgreSQL with backup and release tooling.
- Configuration: migration command, backup, rollback process.
- Procedure: rehearse populated and empty upgrades, backup, rollback, and post-migration checks.
- Staging: yes. Destructive: rollback rehearsal can be destructive; isolate and back up.

No credentials are present or required in the repository. Never commit or print provider secrets. Local deterministic tests remain necessary but cannot close these external/deployment B rows.
