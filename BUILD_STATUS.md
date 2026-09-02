# TickVendor Build Status

## Recovery Audit — 2026-08-31

- Recovery checkpoint: Git initialized; pre-repair state committed as `f8206db`.
- Valid and preserved: authoritative documents, the small database engine/session/Base
  scaffold, and the project virtual environment.
- Corrupt/incomplete at takeover: `src/config.py` imported a nonexistent
  `src.config.tickeven_settings` package; `src/main.py` had no FastAPI application;
  no model package, API routes, migrations, tests, dependency manifest, `.env.example`,
  logging, error envelope, or validation architecture existed. The local SQLite database
  contained no schema.
- Environment: `venv/Scripts/python.exe` is Python 3.13.14 and imports the declared
  foundation dependencies. Dependencies are now declared in `pyproject.toml`.
- Architecture finding: the takeover state did not match the specification beyond a
  minimal SQLAlchemy foundation. `src/database.py` is now restricted to engine, session,
  Base, foreign-key enforcement, and initialization helpers; models are modular under
  `src/models/`.
- Verification: automated tests pass (38), Ruff passes, source compilation passes,
  SQLite foreign keys are enabled, and `/health` plus standardized validation errors work.
- Remaining warning: FastAPI's current TestClient emits an upstream Starlette/httpx
  deprecation warning; it does not fail tests.
- Completion boundary: recovery, foundation, core model schema, migration, focused database
  constraints, and the initial authentication API are verified. Business services, complete
  RBAC, remaining APIs, payment adapters/webhooks, frontend/PWA, and end-to-end product
  journeys remain incomplete and must not be represented as finished.
- Latest verification: clean six-revision migration, 47 backend tests, Ruff, Alembic drift check, and frontend production build pass.
- Production deployment artifacts now include Dockerfile, PostgreSQL Compose topology, README,
  production database driver, and environment guidance; live infrastructure remains unverified.

## Current Completion Audit

The repository is not yet specification-complete. Verified backend foundations and core
business services are substantial, but 100+ checklist requirements remain open, primarily:
complete recognition aggregation/automatic awards, full admin configuration APIs, richer
dashboards, complete frontend journeys/screens, full PWA offline/install behavior, upload/image
handling, distributed rate limiting, comprehensive fraud analysis, and live external-provider
verification. These remain active work; no completion claim is made.

## Final Specification Audit — 2026-09-01

The checklist below corrects earlier backend-capability claims that were broader than the
integrated product evidence. TickVendor is not specification-complete or production-ready.

## Product Identity Decision — TickVendor

- [x] Active product branding, application/package metadata, PWA identity, configuration defaults,
  documentation, examples, email subjects, cache namespaces, and canonical URLs use TickVendor and
  `https://tickvendor.com` (with `https://www.tickvendor.com` allowed for production CORS).
- [x] Historical recovery text retains the former `src.config.tickeven_settings` identifier because
  it documents the exact pre-repair broken import. Legacy installer paths retain the old repository
  directory name because they are isolated historical machine-specific artifacts, not active product
  identifiers; Git history, Alembic revision IDs, and database objects were not rewritten.

## V1 Payment Decision — Paystack

- [x] Paystack is TickVendor's required and default V1 production provider. Stripe and Flutterwave
  remain isolated optional/future adapters and are not V1 release blockers.
- [x] Paystack initialization uses minor currency units; authoritative verification validates the
  provider reference, amount, currency, and successful status before order/ticket activation.
- [x] Payment initialization replay is scoped to the same order/provider/amount/currency, reuses the
  stored checkout URL without another provider call, and rejects conflicting key reuse.
- [x] The webhook endpoint accepts Paystack's real `x-paystack-signature`, verifies HMAC-SHA512,
  ignores non-`charge.success` events, and preserves successful-payment replay idempotency.
- [ ] Exercise Paystack initialization, verification, webhook replay, failure, and refund behavior
  with real Paystack test credentials; automated tests use deterministic HTTP/provider fakes.
- [ ] Implement Paystack provider-side refund initiation and reconciliation before enabling paid
  refunds in production.

- [x] Add the participant frontend shell with real registration/login, session restoration, logout,
  responsive navigation, event search/detail, profile summary, notification view and encrypted ticket
  wallet/QR integration; ticket catalog and free/paid acquisition handoff are now wired to real APIs.
- [x] Add participant attendance UI using authoritative check-in and peer-candidate/confirmation APIs,
  with ticket selection, geolocation permission handling, pending/error states and no client-side
  qualification reimplementation.
- [x] Add participant task navigation and real assignment/task browse plus evidence submission UI;
  authoritative backend statuses and rewards remain the source of truth.
- [x] Add participant Impact/Recognition view for authoritative Impact Points, current/next rank,
  rank history, badges, milestones and privacy-aware leaderboard data.
- [x] Integrate the participant Tasks, Impact/Recognition and ProfileEditor views into reachable
  application navigation with real API calls and verified frontend build/lint.
- [x] Participant integration preserves session-scoped credential storage, authoritative payment
  status API support, enriched QR wallet display, attendance/task/recognition/profile navigation,
  and offline-wallet encryption/service-worker policy checks.
- [x] Add an authoritative payment-return view that queries ownership-protected payment status,
  distinguishes pending/success/failure/unknown/network states, and bounds polling without trusting
  provider redirect parameters.
- [x] Add Playwright Chromium browser verification with deterministic participant shell and payment
  return scenarios; live backend/provider E2E remains separately unverified.
- [x] Add an isolated local E2E database seeder/backend process and pass a real browser-backed
  participant free-ticket acquisition, wallet refresh, and QR persistence journey.
- [x] Real participant Playwright flow now resolves the active community before loading assigned
  tasks, avoiding the prior placeholder route and proving the seeded backend task surface is reachable.
- [x] The real participant browser flow now covers free acquisition, QR wallet refresh, attendance,
  task evidence submission, and Impact/Recognition navigation against the isolated local backend.
- [x] Participant browser acceptance coverage includes deterministic geolocation-denied attendance
  handling without introducing client-side qualification logic; the complete peer-required path remains open.
- [x] Isolated participant E2E fixtures now include a second active peer and required peer verification;
  Playwright covers candidate loading and successful confirmation through the real UI/backend.
- [x] Participant browser regression covers the full local free-ticket path through QR, attendance,
  task evidence submission and Impact/Recognition, plus geolocation-denied handling and peer confirmation.
- [x] Participant browser acceptance now closes the task reward loop: organizer authorization verifies
  submitted evidence, participant refreshes the verified assignment, and Impact/Recognition is reloaded
  from authoritative backend state. Duplicate reward replay remains covered by backend tests.
- [x] Add role-aware organizer dashboard navigation and real dashboard metrics from the organizer
  summary API; participant navigation remains unchanged and dashboard access remains backend-authorized.
- [x] Organizer Playwright coverage verifies an organizer can open the real dashboard metrics while
  participant sessions do not receive organizer-dashboard navigation.
- [ ] Complete the remaining participant frontend journeys: ticket acquisition, check-in result,
  peer confirmation, tasks, contributions, achievements, milestones, ranks, community selection,
  profile editing/privacy controls, and complete loading/error states.
- [ ] Complete organizer/admin frontend journeys: event creation/edit/publish, ticket setup and
  attendee management, QR scanning, attendance review, task/member/contribution management,
  analytics, audit log, and all data-driven recognition/configuration screens.
- [x] Add tenant-authorized PointRule listing/upsert and append-only manual Impact Point adjustment
  APIs with input validation and audit-backed mutations.
- [ ] Complete remaining server-side configuration APIs for attendance/verification rules,
  contribution bands/caps, notification rules, and leaderboard visibility.
- [x] Add community-scoped contribution reward-band create/update APIs with amount-range, overlap,
  reward/cap validation, tenant authorization, enable/disable handling and audit records.
- [x] Add community/organization creation/editing, logo metadata, membership listing/invitation,
  role/status management, tenant authorization, profile-privacy filtering, and privileged audit
  records through product-facing community APIs.
- [ ] Add audit-log query/review and authorized manual-point-adjustment APIs.
- [x] Add privileged tenant-scoped audit-log query API with actor/action/target/time filters,
  bounded pagination, deterministic ordering and recursive sensitive-field redaction.
- [x] Freshly verified audit API access is restricted to community administrators with filter and
  redaction coverage.
- [x] Attendance policy validation enforces that required peer verification is enabled, requires at
  least one confirmation, and cannot require more confirmations than the configured peer limit.
- [x] Attendance policy validation also requires every configured verification method to remain
  enabled, preventing impossible QR, GPS, or organizer verification combinations.
- [x] Add authenticated participant community context listing for active memberships, excluding
  invited/left memberships and preserving tenant isolation.
- [x] Extend participant notification UI with authenticated loading/error/empty handling,
  read-state synchronization and preference controls for in-app, email, push and muted types.
- [x] Wire the authenticated participant community-context endpoint into a reachable Communities
  view showing active memberships and privacy-safe community metadata.
- [x] Wrap lazy-loaded payment-return rendering in an explicit loading boundary so status navigation
  cannot expose a blank screen while the authoritative payment view loads.
- [x] Add participant ticket catalog and authoritative payment-status API; public ticket inventory
  excludes hidden/invite-only types and payment status is restricted to the owning user/order.
- [ ] Integrate `evaluate_recognition` into verified business transitions or a durable job so
  milestone/badge rewards and notifications happen automatically; task/activity/contribution and
  qualifying attendance verification now invoke it, but end-to-end recognition tests remain.
- [x] Execute active `AchievementRule.reward_definition` Impact Point and badge rewards through a
  persisted per-rule/user award, stable idempotency keys, tenant isolation, audit and deduplicated
  notification; malformed definitions fail safely before commit.
- [x] Recognition tests verify combined AchievementRule Impact Point and badge execution is
  idempotent across repeated evaluation, with exactly one award, reward transaction, audit entry,
  and notification.
- [x] End-to-end attendance recognition test covers geofence evidence, configured qualification,
  attendance points, milestone/badge/AchievementRule rewards, and replay-safe recognition effects.
- [x] Recognition coverage includes cross-community isolation for AchievementRule evaluation and
  reward transactions.
- [x] Rank progression history persists qualifying rank achievements with tenant/user/rank
  uniqueness, deterministic reevaluation behavior, and profile exposure; downward punitive changes
  are not introduced.
- [x] Dedicated rank progression tests cover no qualification, initial rank, unchanged reevaluation,
  upward transition, non-point requirements, duplicate prevention, audit/notification counts, and
  highest configured ordering behavior.
- [x] Rank qualification and profile next-rank reporting share the same complete configured
  qualification logic, including non-point requirements.
- [x] Profile rank reporting uses the complete configured rank qualification service and exposes rank
  history through the authenticated community profile response.
- [x] Add authenticated profile metadata/privacy updates and enforce public/member/private visibility
  for profile retrieval and global search, including owner and shared-community access rules.
- [x] Apply the profile visibility policy to community member views and all exposed leaderboard
  entries; private profiles are excluded and member listings redact private profile fields.
- [x] Expose enabled community leaderboards through tenant-authorized APIs with configured metric,
  period, bounded limit, privacy filtering, and deterministic score/user ordering.
- [x] Add authorized leaderboard configuration administration with validated metric/period, enabled
  state, bounded limits, tenant scope and audit records.
- [x] Add event-scoped and weekly/monthly time-window scoring semantics to leaderboard queries with
  UTC-aware filtering and event/community validation.
- [x] Add durable scheduled notification work items and a locally executable worker with conditional
  claiming, preference suppression, bounded retry/backoff, terminal failure state, and deterministic
  local delivery idempotency. SQLite claim behavior is locally verified; PostgreSQL multi-worker
  concurrency and provider-accepted-before-crash delivery remain live/external verification. The
  worker test matrix covers due/future work, replay, preference suppression, retry, terminal failure,
  and already-processing claims.
- [x] Attendance/verification configuration is exposed through an authorized event-scoped API with
  validation for methods, geofence radius, peer limits, tenant scope, and audited mutations.
- [ ] Provide production email and push senders; current defaults are in-memory adapters only.
- [x] Provider verification returns authoritative amount, currency, reference, and status and the
  payment service rejects mismatches before activation (deterministic contracts verified locally).
- [ ] Integrate provider-side refunds for paid orders and reconcile webhook/provider refund state;
  current refund logic transitions local Payment/Ticket/Order records only.
- [x] Paystack webhooks accept the real signature header and validate `charge.success` before
  activation; optional/future provider webhook headers are outside the V1 release boundary.
- [x] Payment initialization idempotency is scoped to the same order/user relationship, provider,
  amount, and currency; valid replay returns the stored checkout and conflicts are rejected.
- [x] QR attendance verification requires organizer/admin/event-staff authorization and an
  authorized organizer approval/rejection API enforces event/tenant scope.
- [x] Enforce event attendance-method configuration (`peer_confirmation_enabled`,
  `qr_attendance_enabled`, `organizer_verification_enabled`) at service boundaries.
- [x] Enforce configurable peer confirmation deadline and per-confirmer maximum, self/duplicate
  prevention, valid-attendee eligibility, and configurable required verification-method combinations.
- [x] Configurable peer candidate selection exposes bounded, deterministic eligible attendees while
  excluding self and previously submitted confirmations; organizer review API remains available for
  authorized override outcomes.
- [x] Award attendance Impact Points idempotently after check-in and resolve the configured central
  PointRule; concurrent Impact Point key races return the existing transaction.
- [x] Task verification, its audit record, notification, and reward insertion share one controlled
  database commit; injected reward/audit/notification failures roll back the primary transition and
  successful retry is exact-once for those effects.
- [x] Recognition evaluation intentionally runs after the primary task transaction; its separate
  failure cannot roll back the durable task/reward/audit/notification transition and remains
  idempotent for retry.
- [x] Enforce hidden/invite-only ticket visibility during ordering.
- [x] Enrich My Tickets with event, date/time, venue, ticket-type, status, QR and order data plus
  upcoming/used/cancelled grouping.
- [x] Enforce task assignee and event tenant membership.
- [x] Add tenant-authorized task and participant-assignment browse APIs with community filtering.
- [x] Add task overdue handling and `verification_required` semantics: required tasks await review,
  non-required tasks qualify on completion, overdue tasks reject late completion, and rewards resolve
  through central PointRule policy.
- [x] Add task attachments and evidence attachment support as validated URL metadata with bounded
  cardinality and tenant-authorized task/submission flows.
- [x] Organizer/admin attendance review APIs list flagged records with event, participant, reason
  and open/cleared/confirmed/rejected filters, preserve original signals, and resolve outcomes with
  tenant authorization and audit records; duplicate check-ins retain `duplicate_check_in` evidence.
- [ ] Add production-grade distributed rate limiting for horizontally scaled deployment.
- [ ] Expand README/project documentation to cover architecture, API/authentication, migrations and
  seeds, payment providers/webhooks, geolocation, PWA, recognition/admin configuration, and deployment.
- [ ] Add browser/E2E coverage for the participant, organizer, and community-administrator journeys;
  current frontend checks are source/runtime policy scripts rather than browser interaction tests.
- [ ] Provide the complete development/demo seed dataset required by the specification (users,
  organizer, community, events, tickets, tasks, badges, ranks, milestones, and activities), clearly
  separated from production seeds; current seeds primarily cover configurable business rules.
- [ ] Replace local filesystem-only image storage with configured production object storage and
  verify upload delivery/authorization in the deployed environment.
- [ ] Verify PostgreSQL migration/application behavior, production deployment, HTTPS/TLS, CORS,
  monitoring/error tracking, and live Paystack/email/push providers. Optional Stripe/Flutterwave
  verification is future work and does not block V1.

## Implementation Checklist — Grouped by Dependency-Aware Subsystem

### Foundation / Architecture
- [x] Project structure and configuration (venv, validated settings, declared packages)
- [x] Application structure establishment (FastAPI factory, health endpoint, model registry)
- [x] Initial 31-table model schema and Alembic migration (clean upgrade/check verified; 60 foreign keys, 88 indexes including SQLite auto-indexes)
- [x] Initial versioned API structure (`/api/v1`, router modules, Pydantic request/response schemas)
- [x] Authentication lifecycle (registration/login/me, bcrypt/JWT access tokens, email verification, password reset, rotating hashed refresh sessions, logout/reset revocation, test email adapter)
- [x] Authorization foundation (platform roles, community role hierarchy, active membership isolation, ownership helper, negative boundary tests)
- [x] User/Profile schema: UUIDs, email/password hash, platform role, verification/activity state, name, username, photo, bio, location, interests, skills, privacy
- [x] Organization schema (owner, identity, verification, active state)
- [x] Community/Membership schema (organization tenancy, multi-community users, scoped roles/status, uniqueness)
- [x] Configuration/environment files (`Settings`, `.env.example`, deployment-secret guard)
- [x] Error handling architecture (stable validation/internal-error envelopes)
- [x] Logging/observability foundation (JSON logs, correlation IDs, secret redaction, safe error hook)
- [x] Validation architecture (Pydantic settings and FastAPI request validation)
- [x] Shared validated pagination and stable API error envelope types/interfaces
- [x] CI/pre-commit quality gates (Ruff, pytest, clean migration check, Gitleaks secret scanning)
- [x] Explicit DB policy (SQLite for development/test only; staging/production require server DB)
- [x] DB dependency rollback/close behavior verified
- [x] Legacy machine-specific installers isolated under `legacy_setup/`; `pyproject.toml` is authoritative

### Events Subsystem
- [x] Event/Venue/EventStaff schema (publishing states, physical/online/hybrid location, attendance configuration, scoped staff roles)
- [x] Event creation API (validated basic info, date/time, location, attendance settings, tenant organizer boundary)
- [x] Event editing with owner/community-admin/super-admin authorization
- [x] Event publishing/unpublishing lifecycle
- [x] Event discovery/detail APIs (published-only browse, search, category, upcoming, pagination)
- [x] Event filtering by category, city, free/paid and upcoming status
- [x] Event chronological/reverse-chronological sorting
- [x] Nearby event API validates coordinates/radius, filters upcoming geocoded events by Haversine distance and sorts nearest-first
- [x] Upcoming events view
- [x] Free vs paid events filtering
- [x] Event categories are database-configurable with all specified defaults and role-protected administration
- [x] Event tags
- [x] Public organizer profiles expose identity, description, verification and published event history
- [x] Owner/admin-authorized event cover-image upload validates MIME, magic bytes and size, stores safely and audits changes

### Ticketing Subsystem
- [x] TicketType/Ticket/Order/Payment schema (inventory constraints, secure public/QR IDs, lifecycle states, provider references, idempotency)
- [x] Ticket type creation API with tenant ownership and inventory/sales validation
- [x] Ticket type properties: name, description, price, quantity, sales start/end, visibility, max per user
- [x] Ticket generation: secure public ID and opaque QR token linked to attendee/event/type/order
- [x] Ticket lifecycle states implemented: reserved, pending payment, paid, active, used, cancelled, refunded, expired
- [x] Duplicate ticket use prevention and staff/tenant-authorized validation
- [x] Idempotent order creation, free-ticket activation, inventory/max-per-user enforcement
- [x] V1 Paystack contract and HTTP adapter, initialization/authoritative verification APIs, real signed idempotent webhook path, plus isolated optional Stripe/Flutterwave adapters (live verification externally blocked)
- [x] Payment state enforcement and server-side amount/currency/provider verification
- [x] Ticket activation upon verified payment confirmation
- [x] Ticket activation flow for free and provider-verified paid orders
- [x] Owner-authorized order refund transition updates payment and unused tickets
- [x] Owner-authorized ticket cancellation with state guards

### Attendance Subsystem
- [x] Attendance/Verification/PeerConfirmation schema (independent attendance, layered signals, confidence/review fields, duplicate prevention)
- [x] Idempotent attendance record/check-in API independent from ticket purchase
- [x] Attendance lifecycle states implemented: not checked in, checked in, GPS/QR/peer/organizer verified, rejected
- [x] Geofenced attendance with coordinates, radius, opening/closing windows
- [x] GPS verification with Haversine distance, accuracy capture, and review flag fallback
- [x] QR attendance verification API with event/attendee/ticket matching and idempotent signal
- [x] Organizer verification/rejection with authorized verification signal and confidence update
- [x] Peer confirmation service with eligibility, self/duplicate prevention, and configurable threshold
- [x] Attendance confidence/status is recalculated from weighted GPS, QR, peer and organizer signals with explicit organizer rejection precedence
- [x] Duplicate QR scans/check-ins, time windows, geofence, low-accuracy, reciprocal-peer and repeated-peer review flags are implemented and tested
- [x] Conservative, idempotent impossible-location transition review flags use valid GPS verification history, preserve attendance state, and include false-positive coverage
- [x] Repeated valid-GPS location bursts are conservatively flagged with machine-readable review reasons and no automatic punishment
- [x] GPS fallbacks: QR and organizer verification
- [x] Location permission handling provides denied, timeout, unavailable and low-accuracy paths with QR/organizer fallbacks
- [x] Attendance UI explains location purpose, requests it only on user action and does not continuously track

### Activities / Tasks Subsystem
- [x] Task/TaskAssignment/TaskSubmission schema (priority, lifecycle, evidence, verification, assignment uniqueness)
- [x] Activity/Contribution schema (five engagement dimensions, monetary/non-monetary types, verification state)
- [x] Tenant-authorized task creation service
- [x] Task assignment to participants
- [x] Enforced task assignment lifecycle states
- [x] Task submission with evidence and assignee ownership
- [x] Organizer/admin task verification
- [x] Idempotent Impact Points awarded only after configured verification
- [x] Configurable community activity recording/verification supports service and leadership categories beyond attendance/tasks
- [x] Monetary/equipment/materials/volunteer-time/services/resources contribution types plus arbitrary activity types
- [x] Contribution recording/verification service with amount, currency, purpose, date/reference and tenant authorization
- [x] Configurable database contribution bands drive idempotent rewards
- [x] Configurable per-user contribution reward caps prevent financial reward dominance

### Impact Point / Reward Engine
- [x] ImpactTransaction schema (auditable status, source references, reversals, unique idempotency key)
- [x] Centralized database-backed Impact Point award service
- [x] Database-backed PointRule defaults and community override structure
- [x] Default point values are database seeds and community-overridable; contribution/special rewards remain configurable
- [x] Point values are resolved centrally from PointRule/ContributionBand, not embedded in feature components
- [x] Impact transactions record user, source, points, timestamp, community, optional event/task, reason and status
- [x] Append-only ImpactTransaction history with explicit reversal references
- [x] Database-unique idempotency keys prevent duplicate rewards
- [x] Attendance/task/contribution/activity/recognition rewards use stable unique references

### Multi-Dimensional Engagement
- [x] Participation dimension tracked through attendance/events
- [x] Execution dimension tracked through verified tasks
- [x] Contribution dimension tracks financial and non-financial contributions
- [x] Service dimension tracked through verified activities
- [x] Leadership dimension tracked through verified activities
- [x] Tenant-isolated member profile API presents participation, execution, contribution, service and leadership dimensions

### Milestone Engine
- [x] Milestone/MilestoneRequirement schema (community-scoped configurable metrics, operators, thresholds, rewards)
- [x] Configurable milestone qualification service using database metrics/operators
- [x] Metrics include tenant-scoped points, attendance, tasks, contributions, service, leadership, peer confirmations, event participation and consecutive verified-activity days
- [x] Idempotent configurable Community Builder seed: 300 Impact Points, 10 verified attendances, 5 completed tasks, 1 community contribution
- [x] Idempotent automatic milestone awards, reward transactions, and notifications
- [x] Milestone definitions and requirements are configurable through tenant-admin API

### Rank System
- [x] Rank/RankRequirement schema (community-scoped points, ordered progression, activity/milestone/badge references)
- [x] Database-configured point-based current-rank evaluation foundation
- [x] Idempotent configurable rank seed thresholds: Starter (0–49), Active Member (50–149), Contributor (150–299), Community Builder (300–499), Community Leader (500–799), Impact Champion (800+)
- [x] Rank qualification evaluates configured activity-count, milestone and non-revoked badge requirements in addition to minimum points
- [x] Tenant admins define ranks through validated, audited API without code changes
- [x] Member profile API reports current rank, next rank threshold and remaining Impact Points

### Badge System
- [x] Badge/BadgeAward schema (configurable JSON requirements, visibility/rewards, idempotent award and revocation history)
- [x] Idempotent badge award primitive; full automatic rule evaluation remains pending
- [x] Badge properties include name, description, icon, category, requirements, reward points and visibility
- [x] Idempotent configurable badge seeds: First Step, Regular, Consistent, Task Starter, Doer, Community Helper, Facilitator, and Community Builder
- [x] Idempotent automatic badge awards from configured condition trees with rewards/notifications
- [x] Tenant-admin badge configuration API validates safe rule trees and audits changes

### Achievement Rule Builder
- [x] AchievementRule schema (versioned condition tree and reward definition for extensible operators)
- [x] Tenant-admin achievement rule API supports validated condition/reward definitions
- [x] Safe evaluator supports AND, OR, >=, <=, =, Count, Sum, Streak, and Unique event count
- [x] Idempotent configurable Community Champion rule seed: attendance >= 20, tasks >= 10, peer confirmations >= 10, leadership >= 3, Impact Points >= 500, reward badge + 50 points
- [x] Achievement evaluator supports safely registered additional aggregate rule types without changing condition-tree evaluation

### Streaks (Optional)
- [x] Optional 3-event attendance, 5-task completion and 4-week activity streak rules are configurable and seeded disabled by default
- [x] Tenant administrators can enable/disable streak achievement rules through an audited API
- [x] Streaks are opt-in, disabled by default and use restrained recognition without automatic point rewards

### Member Journey / Profile
- [x] Achievement timeline API starts with community membership and includes chronologically ordered badge and milestone awards
- [x] Member profile API contains photo, name, username, rank, Impact Points, next-rank progress, badges, milestones, attendance, tasks, contributions, service/leadership dimensions and timeline
- [x] Privacy-aware public/private profile API and authenticated Impact Point summary foundation

### Leaderboards (Optional)
- [x] Tenant-isolated enabled leaderboards support overall Impact Points, attendance/event participation, verified tasks, service and leadership metrics
- [x] Administrators can disable leaderboards through configuration state
- [x] Overall leaderboard uses auditable Impact Points rather than raw monetary contribution amounts

### Event Engagement
- [x] Tenant-authorized event summary covers tickets, check-ins, verified attendance, tasks, contribution amount, badges earned and Impact Points

### Organizer Dashboard
- [x] Organizer dashboard API covers upcoming/total events, tickets, revenue, registrations, attendance/verification, pending tasks, contributions, engagement, top participants and achievement distribution

### Community Dashboard
- [x] Tenant-scoped community analytics covers members/active members, events, tickets, attendance, tasks, contributions, revenue, Impact Points, rank/badge distributions, participation trends and 30-day retention

### Notifications
- [x] Notification schema (in-app payload and read state)
- [x] In-app notification creation/list/read APIs with per-user ownership
- [x] Per-user in-app/email/push preferences and muted notification types
- [x] Ticket/task/badge/milestone notifications and idempotent event, attendance-opening, milestone-proximity and pending peer-confirmation prompts are wired
- [x] Email notification provider abstraction and deterministic in-memory adapter honor user preferences
- [x] Push notification provider abstraction and deterministic in-memory adapter honor user preferences

### Search
- [x] Global search covers events, organizers, public communities, privacy-permitted members and membership-authorized tasks
- [x] Composite indexes support filtered event, community, profile and authorized task search paths

### Event Categories
- [x] Database-backed EventCategory configuration and idempotent default seeds
- [x] All specified default categories are database-backed and seeded idempotently
- [x] Platform administrators can add/edit categories through validated, role-protected APIs

### Community System
- [x] Tenant-authorized community detail exposes name, logo, description and isolated aggregate counts for members/admins, events, tasks, activities, contributions, ranks, badges and milestones
- [x] Users can belong to multiple communities through unique community/user memberships
- [x] Community data isolation enforced in authorization/services with cross-tenant negative tests

### Event Organizer Profile
- [x] Public organizer profile API shows name, profile image, description, published past/upcoming events and email verification status

### Admin Audit Log
- [x] AuditLog schema (actor/community/action/target/timestamp/metadata; append-only design)
- [x] Audit tracking covers event creation/changes, ticket changes, attendance overrides, task/contribution verification, point adjustments, badge awards/revocations, rank changes and user role changes
- [x] Append-only audit helper persists actor, community, action, target, timestamp, metadata

### Manual Point Adjustments
- [x] Tenant administrators adjust Impact Points through immutable transactions
- [x] Every adjustment records amount, reason, administrator, timestamp and transaction ID
- [x] Adjustments produce append-only audit entries; scores are never silently modified

### Data Model
- [x] Normalized modular database architecture covers all named core entities plus auth/config/award/preferences extensions
- [x] UUID primary keys and secure public/token identities
- [x] Created/updated timestamps on mutable entities; append-only audit entries carry occurred_at
- [x] Durable event/community resources support indexed soft-deletion timestamps; event deletion is authorized, audited, idempotency-guarded and excluded from public reads
- [x] Foreign keys, uniqueness, check constraints, lifecycle indexes and idempotency constraints
- [x] Secure public ticket identity/QR tokens; internal UUID exposure remains limited to authenticated/resource APIs

### Security
- [x] Pydantic input validation for implemented APIs
- [x] Framework JSON encoding and React escaped rendering
- [x] Server-side authorization and resource ownership checks on sensitive implemented flows
- [x] Platform/community RBAC with tenant isolation and negative tests
- [x] In-process rate limiting foundation (distributed production backend still required for horizontal scale)
- [x] Cookie-authenticated mutations require an allowed Origin and constant-time double-submit CSRF token; bearer requests remain exempt
- [x] Secure authentication lifecycle with opaque one-time and refresh tokens
- [x] Bcrypt password hashing with minimum 12 rounds and length limits
- [x] Hashed rotating refresh sessions, revocation and reset invalidation
- [x] File/image validation helper enforces MIME allowlist, magic bytes, 5 MB cap and safe filenames
- [x] JPEG/PNG/WebP content validation with spoofing tests
- [x] Provider webhook signature boundary, provider/reference lookup, server verification and idempotency
- [x] API validation and secure response headers foundation
- [x] Sensitive implemented operations emit append-only audit records with actor, target, timestamp and metadata
- [x] Authentication abuse controls throttle repeated failures per client/account and reset only after successful login or expiry
- [x] Backend is authoritative; frontend validation is never the sole control
- [x] Implemented sensitive operations authorize server-side

### Privacy
- [x] Location accepted only during attendance verification and not continuously tracked
- [x] Attendance UI explains one-time location use and offers QR/organizer fallbacks
- [x] Users have persisted profile visibility controls
- [x] Private profiles excluded from public profile/search APIs

### Geolocation Implementation
- [x] Browser/device geolocation requested only through explicit user action
- [x] Haversine distance calculation
- [x] GPS accuracy captured and low accuracy flagged for fallback review
- [x] Permission-denied messaging with QR/organizer fallback
- [x] Geolocation timeout handling and retry/fallback messaging
- [x] Location-unavailable handling
- [x] Low accuracy handled by backend review flag and fallback paths
- [x] Unsupported-browser handling
- [x] Fallback methods: QR and organizer verification
- [x] GPS failure does not prevent legitimate fallback verification

### Offline/Low Connectivity
- [x] Cache public event discovery data for offline reuse
- [x] Ticket wallet renders QR codes from an encrypted device-local offline copy and clears it on sign-out
- [x] Support PWA installation with valid manifest icons and a browser install prompt
- [x] Queue and deduplicate non-sensitive notification-read actions locally, then sync on reconnect
- [x] Retry idempotent GET/HEAD requests with bounded exponential backoff for network and transient server failures
- [x] Lazy-load QR generation and enforce a 210 kB maximum production JavaScript chunk
- [x] Service worker excludes authenticated/private API data from its shared cache

### PWA
- [x] Manifest, service worker, and cached offline application shell build successfully
- [x] App icons and install-prompt UX
- [x] Existing participant shell is mobile-first, keyboard navigable, and responsive across narrow and wide layouts
- [x] Existing application screens have responsive narrow/tablet/desktop layouts, accessible focus states, bounded dialogs, responsive forms/grids, and overflow-safe navigation/table patterns