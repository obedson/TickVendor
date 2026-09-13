# Authentication completion — 2026-09-13

## Scope, authority and starting state

Started at `f997e135c84d94229d74e4a140baec45d344df44`. The previous task/reward,
governance, payment and attendance reconciliation remains intact. This is an
authentication pass, not a project-completion assessment.

Specification §6 requires email/password, email verification, password reset,
secure sessions, authorization and profile completion. Its social-authentication
wording is “Optional OAuth/social authentication architecture”; it does not name
Google. The concrete Google provider and shared visibility controls are requested
compatible product extensions. No original specification inventory was invented.

Existing password-reset endpoints, hashed one-time tokens, bcrypt passwords,
verification emails, JWT access tokens and rotating hashed refresh sessions were
already present. The reset UI was absent. Both email adapters incorrectly selected
the verification template even for a password-reset subject, producing a
verification link instead of a reset link. There was no external-identity model
or actual Google/OIDC login; the bearer-token extractor was not a social provider.

## Password recovery and password fields

- Sign In links to `/forgot-password`. `/reset-password#token=...` accepts the
  emailed proof and removes it from the address bar. Both routes work even when
  a stale session is stored. Missing/invalid/expired links have a new-link action.
- Existing `POST /api/v1/auth/password-reset/request` returns the same generic 202
  message for active, absent and suspended accounts, including delivery failures.
  Suspended accounts receive no new email. A successful delivery is suppressed
  for repeat requests for that account within one minute.
- Tokens use 48 random bytes, SHA-256 database representation, reset purpose and
  one-hour expiry. No token is returned in the public request response. SMTP/Brevo
  infrastructure is reused with reset-specific plain text/HTML, configured
  frontend URL, expiry and ignore-if-unrequested guidance.
- `POST /api/v1/auth/password-reset/confirm` conditionally claims an unconsumed,
  unexpired token, updates the existing password, consumes all sibling reset
  links, revokes all refresh sessions and writes a safe audit in one transaction.
  Verification tokens are unaffected. Suspension is never removed, including
  when a token issued before suspension is redeemed afterward.
- Existing policy is shared by registration/reset: at least 12 characters and
  at most 72 UTF-8 bytes. Schema validation now rejects overlong UTF-8 input before
  bcrypt and excludes submitted secrets from auth validation responses.
- Shared `PasswordInput` covers Sign In, Register, new password, confirmation and
  existing-account Google linking. No separate change-password/admin-password
  form exists. Inputs start masked; mode switches clear/remask passwords. Toggle
  buttons preserve values, autocomplete, required validation, labels and keyboard
  operation. Fixed-width controls avoid Show/Hide layout shifts; fields can shrink
  on mobile. Error/status regions receive focus through the existing focus helper.
- Passwords remain component memory only, never form drafts or browser storage.

## Google architecture, routes and linking policy

The backend authorization-code flow uses the official `google-auth` verifier.
The frontend never receives the client secret, Google access token or ID token.
Only `openid email profile` scopes are requested; no Gmail API/offline access.

| Endpoint | Purpose |
|---|---|
| GET `/api/v1/auth/google/config` | Runtime enabled boolean only; unavailable by default |
| GET `/api/v1/auth/google/start` | Create browser-bound state; redirect to Google |
| GET `/api/v1/auth/google/callback` | Claim state once; exchange code and validate identity |
| POST `/api/v1/auth/google/complete` | Redeem proof-bound grant; optionally confirm local password; issue normal sessions |
| Frontend `/auth/google/return` | Safe cancellation/error/linking states and explicit Complete sign-in action |

State, cookie binding and nonce are random; hashes are stored in `google_auth_flows`.
The HttpOnly SameSite=Lax cookie is Secure on HTTPS and scoped to Google auth routes.
State lasts ten minutes and is claimed before the provider exchange. Google PKCE
uses S256; its verifier is derived with a server-secret HMAC over random state.
The official library validates RSA signature/certificates, issuer, audience,
issued-at and expiry. The service additionally validates stable subject, nonce,
authorized-party claim when present, email syntax and boolean verified-email claim.
Token/certificate requests have bounded timeouts; provider exceptions fail closed
without exposing raw responses.

After callback, a two-minute, single-use opaque grant is returned in a fragment,
not an access token. Its SHA-256 challenge binds it to a separate random verifier
stored only in the initiating browser tab's sessionStorage. Possessing a copied
return URL alone is insufficient. The return page clears the URL and asks to
complete sign-in, avoiding automatic duplicate consumption under React StrictMode.
Reloading that cleared return page requires starting again. Expired flow rows are
cleaned on subsequent Google starts. Fixed configured origins/callback path and
no user-supplied return URL prevent open redirects. HTTPS is required except
localhost/127.0.0.1 during development/test.

1. Resolve an existing identity by `(provider, provider_subject)` first. Sign into
   that same user; a changed Google email updates provider metadata only, not the
   local email or account relationships.
2. A new verified identity without a local email match creates a participant,
   generated unique username/profile and **NULL local password**, never a dummy
   password. Normal password login fails safely. A later explicit email-reset
   flow can establish a local password.
3. A same-email password account requires its existing TickVendor password before
   linking. Email match alone never authorizes a merge, including for Google
   accounts using non-Gmail addresses. Wrong proof fails generically; five wrong
   link attempts exhaust that grant. Roles, memberships and user ID remain intact.
4. Multiple case-insensitive matches, another Google subject already attached to
   the user or a passwordless unmatched identity fail safely. Database uniqueness
   on provider/subject and user/provider, plus existing email uniqueness and
   transaction rollback, prevents duplicate links/accounts during races.
5. Suspended linked users are blocked after verified provider proof. Unlinked
   same-email accounts disclose suspension only after valid local password proof.
   No second user is created; private moderation reasons are never returned.
   Restoration permits sign-in again.

Verified Google email marks local email verified for a newly created user, or
for an exact-email local account after password confirmation. This is exclusively
server-side; normal registration verification remains unchanged and no redundant
verification email is sent for Google sign-in.

## Sessions, RBAC, abuse controls and audits

Both login methods call the same token-issuing function, current-user endpoint,
rotating refresh-session model and logout. User row locks serialize password
login, Google session issuance, refresh and reset on PostgreSQL; conditional
refresh/reset/grant claims also reject replay. User IDs remain the authorization
key; no membership, tenant grants or historical business records are merged.

Reset revokes refresh sessions, **not already-issued stateless access JWTs**.
Access tokens retain their configured lifetime (default 30 minutes); this is the
existing session model, not a claim of immediate access-token invalidation.
Suspension is independently checked against current database state.

The existing rate-limiter implementation is reused: normal global request limit,
existing password-login failed-attempt limiter, and a tighter ten requests/minute
per client/path for recovery and Google routes. Redis is used when distributed
limiting is configured; local fallback remains process-local. Per-account reset
cooldown prevents cross-client email flooding within that interval. Generic
responses are not a claim of constant-time SMTP processing.

`auth.password_reset_completed` and `auth.external_identity_linked` audits contain
safe metadata only. Existing successful password login has no separate login
audit, so Google does not introduce a competing login audit policy. Conflicts and
provider failures emit safe security-event reasons. Auth responses are no-store /
no-referrer; auth access-log query arguments are redacted. Password, reset token,
code, grant, verifier, client secret and provider tokens are not audit metadata.
External proxy/provider log handling still needs operator verification.

## Migration and recovery

Revision `d9e0f1a23456`, parent `c8d9e0f12345`, is the single new head. It makes
`users.password_hash` nullable and adds `external_identities` plus short-lived
`google_auth_flows`, constraints and expiry index. Existing passwords, user IDs,
roles, memberships and history are not backfilled or rewritten.

PostgreSQL uses `ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL`.
SQLite requires a batch rebuild. Its connection-local FK pragma is switched off
outside the transaction only for that rebuild, checked with `foreign_key_check`,
then restored in `finally`. Application connections still enable FK enforcement.
Run SQLite migrations with the application stopped and a recoverable backup:
SQLite rebuild/autocommit is not an all-or-nothing production PostgreSQL migration.
The populated test compares every existing table before/after, including actual
profiles, memberships, sessions, tokens, tickets/orders/payments, attendance,
tasks/submissions, Impact transactions, recognition and audit dependents.

Downgrade/re-upgrade is supported before identities are linked. Downgrade refuses
when external identities exist, preventing loss of login mappings. It intentionally
leaves password nullability permissive; never run old password-only code against
Google-only users. Prefer disabling Google with its flag and a forward fix; a
post-use rollback requires a reviewed identity-preserving recovery plan/backup.
No staging database or infrastructure configuration was modified by this pass.

## External setup — operator action still required

1. In Google Cloud, select/create the project and configure Google Auth Platform
   branding/consent (app name, support/developer contact, authorized owned domains,
   homepage/privacy/terms as required). Select the appropriate audience and add
   controlled test users while testing. Request only openid/email/profile scopes.
2. Create an OAuth client of type **Web application**. Register the exact backend
   callback, including scheme, host and path. The documented staging frontend is
   `https://tickvendor-1.onrender.com`. The supplied repository evidence does not
   establish its current backend hostname: read the actual backend service URL
   later and register `<STAGING_BACKEND_ORIGIN>/api/v1/auth/google/callback`
   with the placeholder replaced, identically in Google and `GOOGLE_REDIRECT_URI`.
3. For local testing register `http://localhost:8000/api/v1/auth/google/callback`
   with frontend `http://localhost:5173`. Production requires its actual provisioned
   HTTPS backend callback and frontend origin; e.g. `https://api.tickvendor.com/api/v1/auth/google/callback`
   only **if that backend domain is provisioned**, not an assumption that it exists.
   Use separate staging/production clients. Google Authorized JavaScript origins
   are not required for this backend code flow (no GIS browser credential widget).
4. Later, on the **backend** Render service set `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_AUTH_ENABLED=true`, and
   ensure existing `FRONTEND_URL`/allowed CORS origins match the frontend. Store
   the secret only in the service secret manager. Retain existing Brevo/SMTP,
   database, Redis and signing-key configuration; this pass changes none of it.
5. Install backend dependencies/apply the new migration through the established
   release process before enabling Google. Deploy the new frontend assets through
   that same process. No Google-specific frontend env variable or client secret
   is required. Later Google config changes are runtime backend changes and do
   not require a frontend rebuild; changing the frontend's existing API-base
   build configuration does. Ensure SPA rewrites cover both recovery and return
   routes. Turning the Google flag off preserves existing users/identities.

These are instructions, not actions performed. Google credentials, live Google
login and reset-email delivery have **external verification outstanding**.

## Manual acceptance checklist

- Controlled mailbox: forgot-password generic confirmation, real Brevo receipt,
  correct fragment link, reset/confirm, old password denied/new password accepted,
  replay/expired link denied, other refresh sessions revoked, verification unchanged.
- Google: new user, existing-password confirmation, wrong proof, stable linked
  user, cancellation/provider failure, stale state/grant and copied return URL;
  verify no duplicate account and no secret in browser/network-visible UI/logs.
- Google-only account establishes password explicitly via recovery; both methods
  then resolve the same account. Verify platform/community roles and historical
  tickets/attendance/points/recognition remain unchanged for linked staging users.
- Suspension with both methods, recovery without reactivation and restoration;
  no private moderation note disclosed.
- Desktop/mobile/PWA: redirects/cookies/sessionStorage, keyboard controls/focus,
  password managers, masked defaults, responsive layouts, slow/offline retries.
- Staging PostgreSQL backup/upgrade and concurrent replay behavior; distributed
  rate limiting, edge-log redaction and deployed SPA rewrite handling.

No additional absent §6 implementation was identified in this focused pass.
Reset delivery/browser acceptance and the concrete Google provider are implemented
but verification outstanding, not complete live-provider claims. Other domains
were not reassessed. Matrix rows 6.94/6.96 now reflect these external gates; old
aggregate traceability counts remain historical and were not recalculated.

## Verification record

Final result: 39 focused backend tests passed (two upstream deprecation warnings);
8 frontend auth tests passed; production build including TypeScript, ESLint,
changed-file Ruff and diff whitespace checks passed. Exact command/results are
recorded with this pass in `BUILD_STATUS.md`. Tests use
isolated SQLite and generated RSA keys/fixture certificates, never live Google
credentials. Actual Google-library verification covers valid signed tokens, wrong
audience/issuer, expiry and signature rejection; extra claims and route bindings
have focused tests. Frontend tests execute hooks/handlers in a deterministic
harness, not a claim of browser/Playwright acceptance.

References: [Google OIDC server flow](https://developers.google.com/identity/openid-connect/openid-connect),
[official ID-token verifier](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html),
[Alembic referencing foreign keys](https://alembic.sqlalchemy.org/en/latest/batch.html#dealing-with-referencing-foreign-keys).

## Changed-file inventory

- Configuration/dependency: `.env.example`, `pyproject.toml`, `src/config.py`.
- Backend: `src/api/auth.py`, `src/api/google_auth.py`, `src/main.py`,
  `src/security.py`, `src/security_middleware.py`, `src/logging_config.py`,
  `src/notifications/email.py`, `src/schemas/auth.py`, `src/services/google_identity.py`.
- Models/schema: `src/models/__init__.py`, `src/models/user.py`,
  `src/models/external_identity.py`, `migrations/versions/d9e0f1a23456_google_authentication.py`.
- Frontend: `frontend/src/main.tsx`, `frontend/src/AuthRecovery.tsx`,
  `frontend/src/PasswordInput.tsx`, `frontend/src/auth.css`.
- Tests: `tests/test_auth_recovery_google.py`, `tests/test_google_auth_migration.py`,
  `tests/test_task_evidence_migration.py`, `frontend/scripts/test-auth-recovery.mjs`.
- Documentation: `BUILD_STATUS.md`, `docs/TRACEABILITY_MATRIX.md`, this handoff.
