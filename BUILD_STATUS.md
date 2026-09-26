# TickVendor Build Status

## App icon branding — 2026-09-26

- Publication follow-up authorized: final corrected artwork is byte-identical to the user's supplied PNG (SHA256 comparison). Re-ran focused PWA test and production build successfully before publication; existing Mapbox size warning only. Device installation remains outstanding.

- Connected user-approved ticket/checkmark artwork to the PWA manifest, browser favicon and Apple touch icon. User rejected the initially generated variant; final files use the exact supplied PNG, aspect-preserving resizing and background padding. Versioned filenames and shell cache v6 replace old cached references.
- Local verification: `node frontend/scripts/generate-icons.mjs`, `node frontend/scripts/test-pwa-install.mjs`, frontend `npm run lint`, frontend `npm run build`, and `git diff --check` passed. Build has existing large Mapbox chunk warning. Final corrected 192px icon visually inspected; corrected assets passed the focused icon test. Build ran while the source artwork was being corrected; deployed asset/device acceptance remains outstanding (B).
- No commit, push or deployment. Details: `docs/PWA_ICONS_2026_09_26.md`.

## Attendance geofence evidence and accuracy guidance — 2026-09-25

- Post-deployment follow-up from a real timeout and comparison with the NIPOST enum form: location acquisition now retries temporary timeout/unavailable failures up to three times with 15 seconds per request. Confident in-radius readings remain automatic GPS verification (green in the attendance roster); uncertain in-radius readings enter organizer review without consuming the ticket or awarding recognition; outside-radius readings remain rejected. Attendance Review confirmation now invokes real organizer verification rather than only closing the queue item, and organizer approval consumes the linked active ticket exactly once. Focused backend verification: **12 passed**; frontend location scripts and changed-file Ruff passed. Production build/lint results recorded after final frontend check below.

- Publication follow-up: user authorized commit/push/merge. PR #4 initial CI passed 417 tests and failed the recognition positive-GPS fixture because it omitted accuracy. Supplied 12 m accuracy to its original/replay inputs without changing assertions. Focused `tests/test_recognition_awards.py::test_attendance_recognition_flow_is_idempotent`: 1 passed; changed-file Ruff and whitespace checks passed. CI rerun required before merge.

- Reviewed the staging screenshot against specification sections 14/15/47 and the actual ticket/attendance services. Accuracy uncertainty was compared to radius before distance calculation, and rejected ticket coordinates were discarded. Physical presence does not imply an accurate browser reading; no numerical staging values were available from the screenshot.
- Added shared assessment and durable event-scoped audit snapshots of submitted location, distance in metres, accuracy, venue/radius, operation and outcome. The authorized attendance roster now displays latest rejected attempts and existing GPS/check-out evidence. Failed ticket attempts do not consume tickets or award points. Missing accuracy is not verified. No schema/migration or historical data rewrite.
- Added bounded fresh-location refinement to both participant check-in screens and replaced the misleading outdoor-only advice with measured distance/accuracy/radius and allowed fallback guidance. Fixed ticket check-in/checkout routes that double-serialized their service response.
- Verification: initial focused backend run 36 passed / 1 failed (positive GPS fixture lacked accuracy). Corrected fixture supplies accuracy, with a new missing-accuracy rejection test. Corrected run of `tests/test_attendance_location_evidence.py` and `tests/test_attendance_service.py`: **9 passed**. Ticket holder/entitlement and organizer operations tests from initial run: **29 passed**. Six behavioral frontend location cases and location error/integration script passed. `npm run build`, `npm run lint`, changed-file Ruff and compile checks passed. No full backend or Playwright suite.
- Design, evidence limitations and staging checklist: `docs/ATTENDANCE_LOCATION_2026_09_25.md`. Browser/device and deployed PostgreSQL verification remains outstanding (B). No global traceability counts changed. Changes remain local; no commit, push, deployment or provider/environment changes in this task.

> **How to use this file.** Entries are newest-first. Read the newest entry relevant to your task and consult older sections only when they are relevant. Append or update evidence without rewriting historical verification. Record the exact checks that were actually executed, and keep implementation status separate from verification status.

## Community application / administrator governance — 2026-09-22

- Implemented the user-requested governance extension without changing the original §5 role inventory: independent communities now use `DRAFT -> PENDING_REVIEW -> ACTIVE/REJECTED`, with reversible `ACTIVE <-> SUSPENDED` moderation. Draft/pending/rejected communities are inactive and excluded from ordinary discovery/authority.
- Any active email-verified user may save and submit an independent application. Applicant-only submission is idempotent, audited and notifies active Super Admins. Super Admin review requires a reason and an active verified initial Community Admin; approval atomically activates/verifies the organization, activates the scoped Admin membership and records reviewer/time/reason. Rejection retains application and audit history.
- Community Admin creation authority is organization-scoped: direct creation is allowed only inside an organization containing another active community the caller actively administers. The creator becomes that new community's Admin. Cross-organization creation is denied. Super Admin direct creation requires an explicitly selected verified initial Admin.
- Community authority remains membership-scoped. Only Super Admin can manage Admin roles. New/reactivated Admins require verified email; platform Super Admin authority cannot be duplicated into a membership. The final active Admin and final active verified Admin cannot be removed or suspended until a verified replacement exists. Community restoration requires a verified active Admin.
- Retired ambiguous platform-wide `organizer`/`community_admin` roles. Migration normalizes those unused user-role values to `PARTICIPANT` without modifying authoritative membership rows. Demo/E2E seeds now express Organizer authority through memberships.
- Migration `d5e6f7a8b9c0` follows `c4d5e6f7a8b9`: existing active/inactive communities retain deployed active/suspended meaning, organization-owner provenance is backfilled, and membership/history data is unchanged. Populated SQLite upgrade/downgrade/re-upgrade and PostgreSQL offline SQL compilation pass. Fresh SQLite upgrade to head plus `alembic check` pass; one head is `d5e6f7a8b9c0`.
- Focused backend governance/auth/moderation batch: **39 passed**; final community/application/migration batch after server-draft integration: **14 passed**; final governance state-machine rerun: **8 passed**. Two upstream Starlette/httpx/AnyIO deprecation warnings only. No full backend suite or Playwright run.
- Frontend: production build passed (113 modules) after rerunning sequentially with a local Node heap allowance; lint passed; governance + management source-contract checks **35 passed**. The initial concurrent build/lint attempt exhausted the Node heap before compilation and is not counted as product failure.
- `compileall`, changed-file Ruff and `git diff --check` pass. Detailed design, API/schema behavior, migration policy and manual staging checklist: `docs/COMMUNITY_APPLICATION_GOVERNANCE_2026_09_22.md`.
- External/manual verification outstanding: staging PostgreSQL migration, separate-account draft/submit/review/reject, notification receipt, organization-scope acceptance, replacement-Admin protection, and mobile/keyboard/dialog behavior. No push, deployment, provider configuration or live database operation was performed.

## Organizer least-privilege / RBAC hardening reconciliation — 2026-09-19

Verified final state:

- Organizer no longer receives unrestricted community member directory/contact data.
- Organizer can perform constrained, community-scoped member lookup by exact email / username / name with privacy minimization and capped results.
- Admin retains full community member directory/governance access.
- Organizer management navigation is role-aware; Admin-only views are hidden and stale views resolve safely.
- Attendance/event authority is scoped to event owner, Community Admin, Super Admin, or explicitly assigned EventStaff according to staff-role semantics.
- EventStaff delegation is implemented with assignment/revocation and role-specific authority groups.
- Ticket validation now supports properly assigned EventStaff without broadening community-wide Organizer authority.
- Event analytics are owner/Admin/Super Admin or Manager EventStaff scoped.
- Organizer task management is owner-scoped; Community Admin may manage all community tasks.
- Ticket catalog visibility preserves public-only inventory for ordinary members/unrelated organizers and hidden inventory only for legitimate maintainers.
- Historical task reconciliation documentation received a superseding note rather than rewriting old history.
- `docs/TICKVENDOR_SPEC.md` conflicts were reported, not silently rewritten.

Verification evidence:

- `python -m pytest tests/test_organizer_least_privilege.py -q` — **45 passed**, 2 warnings.
- Related backend regression batch — **28 passed**, 2 warnings.
- Broader backend event/task/ticket regression batch — **81 passed**, 2 warnings.
- `python -m pytest tests/test_ticket_type_api.py -q` — **7 passed**, 2 warnings.
- Full backend, `python -m pytest -q` — **403 passed**, 6 warnings.
- Ruff across all changed Python files — all checks passed.
- Frontend: `npm run build` passed; `npm run lint` passed; `node scripts/test-management-layout.mjs` — **28 passed, 0 failed**.
- `git diff --check` — no whitespace or conflict-marker errors; only the working copy's existing LF→CRLF warnings.
- Vitest was **not run** for `frontend/src/__tests__/managementNav.test.ts`: Vitest is not a project dependency and dependencies were deliberately not mutated for verification alone. No Vitest pass is claimed.

## Full-suite reconciliation — 2026-09-17

- Continued the inherited dirty tree at base `84be0cd` without reset, clean, restore, revert, stash, discard, branch switch, commit, push or deploy, and without any provider, environment, domain or remote-database change. Scope was the four recorded full-suite failures and the two recorded observations only.
- Migration-head test: `tests/test_start_web.py::test_blank_database_migrates_to_current_head` asserted the superseded head `f1a2b3c4d5e6`. It now reads the single expected head from the Alembic script directory and asserts `alembic current` reports it, so it still detects a startup migration that did not run, without breaking when a legitimate revision is added. No revision changed; the single head remains `e0f1a2b34567`.
- Alembic logging side effect (order-dependent payment failure): `migrations/env.py` called `fileConfig(config.config_file_name)` with the default `disable_existing_loggers=True`, which disabled `tickvendor.monitoring` for the rest of any process that ran a migration in-process, so `tests/test_payments.py::test_initialization_failure_releases_pending_ticket_reservation` captured no monitoring records after a migration test. The call is now `fileConfig(config.config_file_name, disable_existing_loggers=False)`; Alembic's root/alembic loggers are still configured and payment behaviour is unchanged. New `tests/test_migration_logging.py` fails if an in-process migration disables or silences the application monitoring logger.
- `/communities/me` contract: the endpoint intentionally returns every membership state for the caller (active, invited, suspended and past), as documented in `docs/GOVERNANCE_MEMBERSHIP_MODERATION_2026_09_12.md` and required by the participant journeys in `frontend/src/Communities.tsx` and `frontend/src/CommunityLifecycle.tsx`. The stale active-only assertion was corrected rather than the endpoint. Coverage now asserts invited and suspended statuses, an invited private community, ordering by membership creation, and that another tenant's membership in a community the caller does not belong to is never returned.
- Event soft deletion: the intended idempotency guard (409 on a repeat authorized delete) was unreachable because `get_event_for_management` hid deleted events as 404. An `include_deleted` path now authorizes a management caller before reporting the already-deleted state, so an authorized repeat delete returns 409, an unauthorized caller still receives 403 with no existence disclosure, and exactly one `event.deleted` audit entry is written.
- Bulk assignment: the constant `ineligible: 0` was removed from the bulk-assignment response. Any per-address eligibility count (non-member, other community, nonexistent account) would make the endpoint an account/tenant enumeration oracle; the existing requester-scoped `members`/`unresolved`/`invalid` categories on the resolution endpoint remain the only safe vocabulary, and `frontend/src/BulkTaskAssignment.tsx` used neither field.
- Promotion deep link: a promoted opportunity beyond the first fetched page fell back to the plain list because no opportunity detail endpoint existed. Added `GET /api/v1/activity-opportunities/{opportunity_id}` behind the discovery visibility predicate now shared with the listing (`_discoverable` in `src/services/opportunity.py`), and `frontend/src/Opportunities.tsx` fetches it once when a promoted id is not on the current page. Draft, deleted, expired, suspended-community and member-only-for-non-member items stay hidden, so no new authorization or privacy surface exists; task promotions still resolve against the loaded task list only.
- Focused verification: `.venv/Scripts/python.exe -m pytest tests/test_start_web.py tests/test_migration_logging.py tests/test_google_auth_migration.py tests/test_task_evidence_migration.py tests/test_participation_migration.py tests/test_payments.py tests/test_participant_communities_api.py tests/test_governance_membership.py tests/test_soft_delete.py tests/test_events.py tests/test_task_staging_reconciliation.py tests/test_participation_reconciliation.py tests/test_activity_opportunities_api.py tests/test_platform_moderation.py tests/test_community_management.py -q` — **66 passed**, 2 upstream deprecation warnings. The payment logging failure was re-verified alone, in the previously reproducing order after `tests/test_participation_migration.py`, and after all in-process migration tests.
- Full backend suite: `.venv/Scripts/python.exe -m pytest -q` — **276 passed**, 0 failed (previously 270 passed, 4 failed), 2 upstream deprecation warnings, 560.61 seconds.
- Ruff: every file changed by this pass is clean. Repository-wide `ruff check .` reports 34 inherited findings: `tests/test_task_type_and_evidence.py` (17), `legacy_setup/install_pkgs.py` (4), `legacy_setup/install_remaining.py` (4), `legacy_setup/setup_venv.py` (3), `tickvendor_settings.py` (3), `tests/test_auth_refresh_behavior.py` (2), `tests/test_free_ticket_flow.py` (1). None were cleaned.
- Frontend: `npm run build` and `npm run lint` both passed. `git diff --check` passed with only the repository's existing LF/CRLF warnings; the untracked files touched (`src/services/task_bulk.py`, `tests/test_participation_reconciliation.py`, new `tests/test_migration_logging.py`) were also checked directly for trailing whitespace and a final newline.
- Migration safety: disposable-database `alembic upgrade head` followed by `alembic check` reported "No new upgrade operations detected." No schema, model or revision change was made.
- No traceability matrix was regenerated, no completion counts or percentages were recalculated, no historical evidence was rewritten and no global reconciliation was performed.

## Promotion delivery / governance boundary reconciliation — 2026-09-17

- Continued the existing interrupted working tree (inherited promotion model/service/API, `frontend/src/PromotionManager.tsx`, participation-and-promotion migration `e0f1a2b34567`, governance screens). No reset, discard, push, deployment or provider/environment/database change.
- Scope: platform governance and moderation boundaries, Featured/Sponsored lifecycle, promotion delivery authorization and privacy, promotion schedule and placement integrity, placement surfaces, community-scoped events, and member-email disclosure.
- Governance and moderation over users, communities, events, opportunities and tasks require Super Admin, require a reason, write audit history and are reversible; content suspension already blocks discovery, direct use, attendance, task assignment and search, and restoration is covered by `tests/test_platform_moderation.py`. Suspending your own account or any Super Admin account is refused server-side, so platform authority cannot cause a last-admin lockout. Platform authority stays separate from community membership: `require_community_role` grants a Super Admin administrative authority in any community without creating a membership, and only a Super Admin can assign or change community administrator authority. No governance implementation change was required.
- Promotion schedule defect fixed: a client-supplied non-UTC offset was persisted unconverted, shifting the placement window by that offset so an active placement was not delivered. `src/api/promotions.py` now normalizes `starts_at` and `ends_at` to UTC before storage and comparison.
- Promotion delivery defect fixed: two overlapping placements for the same underlying content on one surface returned that content twice, labelled once Featured and once Sponsored. `src/services/promotion.py` now delivers one entry per underlying item, keeping the highest-priority placement.
- Authorization and privacy confirmed unchanged in substance: underlying content authorization is rechecked on every delivery, so suspension, privatization, lifecycle change, closure or expiry of the promoted item stops delivery without recreating the promotion; community-private and member-only content is never promoted; member-only task placements reach only active community members and never anonymous callers; covers are delivered through signed, expiring URLs.
- Featured/Sponsored remains an approved user-requested extension, not an original specification requirement: `docs/TICKVENDOR_SPEC.md` §78 lists event promotion only as a future-ready capability. No requirement was added, removed, deferred or reclassified.
- Community-scoped member events: no implementation required. §7 and §53 define platform-wide event discovery, §39 records events as community-owned data, and §35 requires community administrators (not members) to see community events. `frontend/src/CommunityMember.tsx` therefore keeps the honest platform-wide "Browse all events" action.
- Member email: the inherited organizer-and-above boundary is consistent with the other organizer workflows that already resolve member emails (task assignment candidates and the attendance roster both require community organizer). Ordinary members receive no member emails, and invite by email or username stays administrator-only. Frontend rendering cannot widen the boundary because it only displays fields the backend supplies. No change; focused coverage added for the organizer tier and suspended membership.
- Focused verification: `.venv/Scripts/python.exe -m pytest tests/test_participation_reconciliation.py tests/test_platform_moderation.py tests/test_governance_membership.py tests/test_participation_migration.py -q` — **26 passed**, 2 upstream deprecation warnings; the extended promotion/email file re-run passed **17**. Ruff passed on all three changed files. `git diff --check` passed; the changed files are untracked, so they were also checked directly for trailing whitespace. No full pytest, no Playwright, no frontend build (no frontend file changed).
- No global traceability counts or percentages were recalculated, no historical evidence was rewritten, and no full-spec reconciliation was performed.

## Authentication recovery / Google completion — 2026-09-13

- Continued from `f997e135c84d94229d74e4a140baec45d344df44`, preserving the completed task/reward/governance/payment/attendance pass. No push, deployment, external configuration or live provider operation.
- Root causes: reset routes/tokens existed but no recovery UI; the shared token-email helper rendered verification links even for reset emails; no actual OIDC provider or stable external identities existed. Reset UI/template and shared accessible masked-by-default password controls now cover every actual password form.
- Existing auth/session primitives are reused. Reset requests remain generic even on delivery failure, suppress repeat emails for one minute, claim expiring hashed tokens once, consume sibling reset tokens, revoke refresh sessions and audit safely. Email verification and suspension remain intact; existing stateless access JWTs retain their configured expiry (default 30 minutes).
- Google uses server-side authorization-code OIDC with the official verifier, state/cookie/nonce/PKCE, fixed configured redirects and a short-lived proof-bound return grant. Stable provider subjects, same-email password confirmation, unique constraints and normal TickVendor sessions preserve accounts/RBAC/history. New Google accounts have NULL passwords; suspension cannot be bypassed by creating a duplicate.
- Google-specific sign-in and visibility controls are user-requested compatible extensions, not fabricated original-spec requirements. §6 reset/session requirements are preserved. Only TV-6.94 and TV-6.96 classifications/evidence were updated to B (implemented but external verification outstanding); no historical/global traceability counts or percentages were recalculated.
- Migration `d9e0f1a23456` → parent `c8d9e0f12345`: nullable local password plus external identities/ephemeral flows. A real populated test caught SQLite FK failure rebuilding `users`; connection-local FK handling now surrounds the rebuild and verifies/restores integrity. Populated rows across profiles, membership, sessions, tickets/payments, attendance, tasks, Impact, recognition and audits are unchanged. PostgreSQL ALTER/DDL compilation passes; single head verified. Downgrade/re-upgrade tested before identity use; downgrade refuses existing external identities and retains permissive password nullability.
- Test corrections addressed only the structurally undersized expired-token fixture and an assertion selecting an unrelated session guard. Production validation was not weakened.
- Final focused backend command: `.venv/Scripts/python.exe -m pytest tests/test_auth_recovery_google.py tests/test_google_auth_migration.py tests/test_task_evidence_migration.py tests/test_auth.py tests/test_auth_refresh_behavior.py tests/test_auth_abuse.py tests/test_notification_email.py tests/test_authorization.py -q --tb=short` — **39 passed**, 2 upstream Starlette/httpx/AnyIO deprecation warnings, 137.22 seconds. Includes generated RSA signatures verified by the real Google library; wrong issuer/audience/expiry/signature, linking/uniqueness/role preservation, reset/session/suspension, rate-limit and secret-redaction checks. No live Google credentials.
- Frontend: `node --test scripts/test-auth-recovery.mjs` — **8 passed**; `npm run build` (TypeScript + Vite) — passed, 97 modules; `npm run lint` — passed. Deterministic hook/handler tests are not browser acceptance. No Playwright or full backend suite run.
- Changed-file Ruff passed for all 17 changed/new Python files. `git diff --check` passed. Final review found no temporary databases, generated assets, real secrets or unrelated domain edits in the intended change set.
- Handoff/configuration/manual acceptance: `docs/AUTH_GOOGLE_PASSWORD_RESET_2026_09_13.md`. Live Google setup/login, reset email receipt, desktop/mobile/PWA/password-manager behavior, staging PostgreSQL upgrade/concurrent requests, distributed limiting and edge-log handling remain external/manual verification outstanding. No additional absent specification-backed auth implementation was identified in this scoped pass; no other domain was reassessed.

## Task / evidence / Impact staging reconciliation — 2026-09-13

- Continued the intentional diff from `6c345166065e7cfd11aab4ee33272b2534a3d5eb`; no restart, discarded work, push, deployment or provider/environment changes.
- Real user staging evidence: video and physical tasks were created/assigned/submitted/reviewed; cards advertised 20/10, but a configured 5-point Task Completion rule produced totals 10 → 15 → 20 and task count 0 → 1 → 2. Missing-rule verification originally returned 409. Suspended sign-in returned generic invalid credentials; forms lacked refresh recovery; action visibility/member identification and long Home loading were reported.
- Root cause: stored task rewards previously acted only as nonzero eligibility flags. Existing tasks retain `legacy_rule` meaning; new `explicit` tasks have bounded rewards. Display uses current effective policy, notifications use posted points, and historical transactions are not rewritten. Positive verification without an active rule still fails rather than silently finalizing with zero.
- Requested compatible extensions, **not additions to the original spec inventory**: embedded quiz grading, opinion-neutral surveys, optional video attention checkpoints and separate platform ceilings. No illustrative 20-point default, LMS, global rank subsystem or guaranteed YouTube watch proof.
- Super Admin controls unique nonnegative source ceilings with reasons/audit; positive community rules/new tasks require configured ceilings. Server award service clamps configured source overrides. Community rule precedence is explicit on PostgreSQL; one community/source rule remains enforced and active global/source gets a partial unique index.
- Server-side grading, answer-key redaction, bounded attempts, persisted results, membership gates, payload-checked replay keys, serialized verification, stable point/notification references, recognition retry and latest-submission queue are implemented. Empty physical evidence requirements are respected.
- Valid password precedes suspended-account 403; invalid/unknown credentials remain generic. Internal moderation notes remain private. Existing governance/membership/archive authority is preserved.
- Encrypted account/community/entity-scoped draft recovery covers task creation/evidence. Shared focus/viewport helper and native dialogs cover changed actions. Home retains three parallel requests with a 20-second deadline/abort/retry; no unproven internet/cold-start cause or measured staging speed improvement claimed.
- Migration `c8d9e0f12345` follows `b7c8d9e0f123`. Populated disposable SQLite upgrade preserves task amount/mode, evidence and posted points; verifies derived ceilings/global-rule cleanup, downgrade/re-upgrade. PostgreSQL offline SQL compiles. Live PostgreSQL execution/concurrency remains verification outstanding.
- Initial focused run: **25 passed / 2 test-assertion errors** (`Notification.body` instead of `message`); corrected assertions passed. A broader run found an old rule-creation fixture without the newly required ceiling; fixture now configures it without removing assertions. Combined selected backend run: **41 passed**; final affected/new-regression rerun: **24 passed**. Two dependency deprecation warnings remain.
- Final frontend task/governance/management checks: **38 passed**. Final `npm run build` (TypeScript + Vite, 94 modules), `npm run lint`, changed-file Ruff and `git diff --check` passed. No Playwright or full backend suite ran.
- Design, security decisions, exact verification commands, migration recovery caveats, changed-file inventory and manual checklist: `docs/TASK_STAGING_RECONCILIATION_2026_09_13.md`. Browser/device/draft recovery/provider receipt/PostgreSQL concurrency and large-community acceptance remain outstanding. Previously identified dedicated create-community UI remains not yet implemented. No overall completion assessment or global traceability count changes.

## Governance / membership / moderation / personal-space continuation — 2026-09-12

- Resumed the existing interrupted working tree from `4a89a0225df39c6b99df28f5f0b305a93588e3dc`; no reset, stash, discard, push or deployment. Prior responsive/media/payment/attendance work preserved.
- Implemented explicit membership access policies and invitation/join/request/leave transitions; backend-enforced Super Admin-only community Admin assignment/demotion, tenant checks, reasons, audits and preference-aware notifications. Closed the legacy admin role-route bypass during final review.
- Added platform inspection and reversible user/community/event/opportunity/task moderation, separate from domain lifecycle; enforced current-action suspension gates, including QR/organizer attendance endpoints missed by the initial shared lookup integration. Read-only event roster/review remains available under existing community authority.
- Added owned, reversible presentation archives for notifications, historical tickets, verified assignments and completed/closed opportunity participation. No financial/attendance/Impact/recognition record deletion or status mutation. Existing failed-reservation wallet filtering and QR credentials preserved.
- Reviewed intentional Community/Platform Admin extraction and component mounting. Added native reason confirmations, searchable/paginated governance, member controls matching authority and membership-aware workspace refresh.
- Migration `b7c8d9e0f123` follows actual prior head `9f0a1b2c3d4e`; single Alembic head. Isolated SQLite previous-head upgrade, constraint/index checks, downgrade/re-upgrade and PostgreSQL SQL compilation pass. Live PostgreSQL execution/concurrency remains unverified.
- Focused combined backend run: **38 passed** (14 selected files; one existing Starlette/httpx deprecation warning). After strengthening the populated evidence-preservation regression, the final governance/moderation/archive rerun passed **9 tests**. Focused frontend governance/management/location/offline tests: **34 passed**. Final TypeScript/Vite build, ESLint, changed-file Ruff and `git diff --check` pass. Route inventory has no duplicate method/path pairs. Local commit identity is reported with delivery.
- Detailed design, exact API/schema inventory, last-Admin decision, immutable-record policy, test commands and participant/Admin/Super Admin acceptance checklist: `docs/GOVERNANCE_MEMBERSHIP_MODERATION_2026_09_12.md`.
- No manual staging or viewport testing claimed. Required external verification includes 320/360/390/414/768/1024/1280px flows, keyboard/dialog behavior, notification delivery, PostgreSQL migration and concurrency. Community creation has an authorized API but its dedicated UI form remains unfinished. No overall completion assessment or authoritative traceability count/percentage changes.

## Spec Reconciliation Remediation Pass 2 — 2026-09-10

Branch: `duo/feature/spec-reconciliation-remediation`

#### FIRST PLATFORM ADMIN BOOTSTRAP — IMPLEMENTED, LOCALLY VERIFIED
- Added `scripts/provision_first_super_admin.py` for the one-time operator bootstrap. It only promotes an existing active, email-verified user when no `super_admin` exists, requires explicit `--confirm`, is not an HTTP endpoint, and records `platform.super_admin_bootstrapped` in the append-only audit log.
- The development/demo seed remains separate and must not be used against staging or production. Default event categories are seeded only when the development/business seed is explicitly run; deployed startup does not mutate business configuration.
- Fixed the Platform Admin user overview to derive email verification from `email_verified_at` rather than the nonexistent `is_email_verified` attribute.
- Focused verification: bootstrap, category authorization, and platform authorization tests pass; Ruff, compilation, and `git diff --check` pass.

### Pass 2 — Task UI, Members Browser, Category API, Static Review Fixes

#### PRIORITY 3 — Category API Design (IMPLEMENTED, verification outstanding)
- Decision: Public category discovery exposed at `GET /api/v1/events/categories` (non-admin route matching project conventions for public reads like events/communities). Mutations (POST/PATCH) remain under `/admin/categories` super_admin-only.
- `OrganizerEvents.tsx` updated to use `/events/categories` instead of `/admin/categories`.
- `PlatformAdmin.tsx` CategoryManager still uses `/admin/categories?active_only=false` (authenticated super_admin route) to see all categories including inactive.
- Category selector UX: loading state, error with retry button, clear "no active categories" message that disables submit (no free-text fallback).
- Bug fixed: `select` was missing from imports in `src/api/admin.py` (would have caused NameError at runtime on `list_categories`).
- New platform admin endpoints: `GET /admin/platform/users` and `GET /admin/platform/communities` (super_admin only) — replaces broken `search?q=` usage in PlatformAdmin.tsx (search requires min_length=2).
- Verification: NOT VERIFIED (Python deps / npm blocked).

#### PRIORITY 4 — Static Review Defects Fixed (IMPLEMENTED, verification outstanding)
- `api.ts`: Added `isBodyReReadable()` guard — FormData and ReadableStream bodies are NOT retried after 401 (prevents double-consumption / empty body on retry). Auth endpoints (auth/login, auth/refresh) are excluded from refresh-on-401 to prevent recursive loops. After a successful refresh, if the retry also returns 401, `clearSession()` is called exactly once.
- `OrganizerEvents.tsx`: Removed `members_only` ticket visibility option (not in backend `TicketVisibility` enum; backend only has public/hidden/invite_only). Category payload sends slug (correct — backend `validate_category` normalizes to slug).
- `PlatformAdmin.tsx`: Fixed user/community listing to use dedicated platform admin endpoints instead of search endpoint.
- Management nav structure verified: OVERVIEW (Dashboard), PROGRAMS (Events, Opportunities, Tasks), PEOPLE (Members, Attendance Review, Check-in), IMPACT (Leaderboard, Recognition, Adjustments), SETTINGS (Point rules, Contribution Tiers, Notifications, Analytics, Audit log), PLATFORM (Platform Admin — super_admin only). Matches spec requirement exactly.
- Verification: NOT VERIFIED (npm blocked).

#### PRIORITY 1 — Task UI (IMPLEMENTED, verification outstanding)
- `Tasks.tsx`: Evidence submission modal now exposes `evidence_text`, `evidence_url`, and `evidence_attachments` (up to 10 URLs) with usable controls. Client-side validation enforces `required_evidence_types` per task config (required fields marked *, block submit). URL format validation with onBlur feedback. Task cards show task-type-specific quick info (video link, social follow link, survey link, referral instructions, physical location).
- `OrganizerTaskQueue.tsx` (full rewrite): Three-view layout — Verification Queue / All Tasks / Create Task. Verification queue shows all evidence types including attachments; reject action prompts for rejection reason. All tasks list with assign-to-member modal. Create task form supports all 6 task types with per-type config fields.
- Backend: `TaskType` enum (general/video/social_follow/survey/referral/physical) added to `src/models/task.py`. `task_type`, `task_config` (JSON), `required_evidence_types` columns added with Alembic migration `a1b2c3d4e5f6`. `TaskCreateInput` validates config keys per task type. `submit_task()` enforces `required_evidence_types` (raises 422 if required evidence missing). Task list API includes new fields in response.
- Referral tasks: use manual/organizer verification (no platform referral tracking exists; anti-abuse note shown in UI; organizer verifies referred users are new/verified accounts).
- Verification: NOT VERIFIED (Python deps / npm blocked).

#### PRIORITY 2 — Members Browser (IMPLEMENTED, verification outstanding)
- Backend: `POST /communities/{id}/members/invite` endpoint added — accepts `identifier` (email or username), looks up user, creates INVITED membership. Privacy-safe (returns 404 for both not-found and privacy-redacted). Self-invite and admin-role escalation guards. Audit record fires.
- `OrganizerMembers.tsx`: Invite form (email/username + role selector). Role management: "Change role" button opens confirmation modal with role selector (disabled when new role equals current). Status display: invited/pending shown with yellow chip. Empty state has "Invite member" action.
- Verification: NOT VERIFIED (npm blocked).

#### Tests Added (Pass 2) — NOT VERIFIED
- `tests/test_task_type_and_evidence.py`: 9 focused backend tests covering task type creation, evidence validation (text/url required), tenant isolation (cross-community task creation denied), member denied on verification queue, ordinary admin denied on category mutations, public /events/categories endpoint.
- `frontend/src/__tests__/api.test.ts`: 7 vitest unit tests for api.ts covering refresh-on-401, single retry, no second retry, concurrent dedup (single refresh promise), failed-refresh sign-out, FormData body guard, auth endpoint exclusion.

#### Checks Executed (Pass 2)
- `python3 -m py_compile src/api/admin.py src/api/events.py src/api/tasks.py src/api/community_management.py src/models/task.py src/models/__init__.py src/schemas/task.py src/services/task.py src/main.py` → Exit 0 (all OK)
- `python3 -m py_compile tests/test_task_type_and_evidence.py tests/test_event_categories_admin.py tests/test_free_ticket_flow.py` → Exit 0 (all OK)
- `git diff --check` → Exit 0 (no whitespace issues)
- Brace balance check on all modified .tsx/.ts files → all balanced

---

## Spec Reconciliation Remediation — 2026-09-10

Branch: `duo/feature/spec-reconciliation-remediation`

### Priority 1 — Central Auth/Session Fix (IMPLEMENTED, verification outstanding)
- Root cause: `api.ts` `refreshSession()` read from `sessionStorage` but did not update live React state; concurrent refresh races were not prevented; all protected calls used stale token props/closures.
- Fix: Canonical `SessionData` type; `addAuthListener`/`persistSession`/`clearSession`/`getLiveToken` exported from `api.ts`; single in-flight `_refreshPromise` prevents concurrent refresh races; `apiJson` always reads `getLiveToken()` before using the prop token; retry-once after 401; invalid refresh triggers `clearSession()` (clean sign-out); React root subscribes via `addAuthListener`; `apiFetchAuth` wrapper for non-JSON authenticated calls.
- All 19 frontend components updated to use `apiJson`/`getLiveToken()` instead of raw `apiFetch` with stale token props.
- Verification: NOT VERIFIED locally (npm registry blocked in this environment; no node_modules). Requires frontend build + browser test in staging.

### Priority 2 — Event Categories (IMPLEMENTED, verification outstanding)
- Root cause: No GET endpoint for categories; `OrganizerEvents.tsx` hardcoded `category: 'community'`; form had no selector.
- Fix: Added `GET /api/v1/admin/categories` public endpoint (no auth required, `active_only=true` by default); `OrganizerEvents.tsx` loads categories from API on mount; renders `<select>` with human-readable names; falls back to text input if API unavailable; default set to first active category.
- Backend test added: `tests/test_event_categories_admin.py::test_list_categories_public_endpoint`.
- Verification: Backend test NOT VERIFIED (Python deps not installed in this environment). Frontend NOT VERIFIED (npm blocked).

### Priority 3 — Free Event Tickets (IMPLEMENTED, verification outstanding)
- Root cause: `acquire()` in `main.tsx` used stale `session.access_token` prop; free ticket path used `apiJson` but with stale token.
- Fix: `acquire()` now uses `getLiveToken() ?? session.access_token`; free ticket path (price=0) calls `apiJson` for order creation and wallet refresh with live token; no Paystack checkout for free orders.
- Backend tests added: `tests/test_free_ticket_flow.py` — covers free ticket acquisition, active status, QR token presence, duplicate protection, and payment initialization rejection for confirmed free orders.
- Verification: NOT VERIFIED (Python deps not installed).

### Community/Organization Admin (IMPLEMENTED, verification outstanding)
- Fix: `managedCommunities` filter now includes `role === 'organizer'` in addition to `role === 'admin'`; uses `apiJson` with live token.
- Tenant isolation: preserved — backend enforces community-scoped authorization on all management endpoints.

### Super Admin / Platform Admin (IMPLEMENTED, verification outstanding)
- New: `frontend/src/PlatformAdmin.tsx` — restricted to `super_admin` role; provides Event Category CRUD (create/edit/activate/deactivate), Platform Users overview, Platform Communities overview.
- Integrated into management workspace nav as "Platform" group (only visible to super_admin).
- Backend: `GET /api/v1/admin/categories` (public), `POST /api/v1/admin/categories` (super_admin), `PATCH /api/v1/admin/categories/{id}` (super_admin) — all existing.
- Verification: NOT VERIFIED (npm blocked).

### Contribution Tiers Wording (IMPLEMENTED)
- Frontend-only: "Contribution Bands" → "Contribution Tiers" in all UI labels, messages, headings, and nav items.
- Backend/API/database identifiers unchanged (`contribution-bands`, `ContributionBand`).
- Description: "Define contribution ranges and the Impact Points members earn for each tier."
- Create button: "Create contribution tier"; Save button: "Save contribution tier"; List heading: "Configured tiers".
- Empty state: "Contribution ranges must not overlap active tiers."

### Audit UX (IMPLEMENTED, verification outstanding)
- `AdminAuditLogs.tsx`: human-readable `friendlyAction()` mapping for 40+ action codes; concise technical code shown below; expandable "Show details" / "Hide details" for raw metadata; `<details>` element for raw JSON.
- Verification: NOT VERIFIED (npm blocked).

### Management UX (PRESERVED)
- Nav structure: OVERVIEW (Dashboard), PROGRAMS (Events, Opportunities, Tasks), PEOPLE (Members, Attendance Review, Check-in), IMPACT (Leaderboard, Recognition, Adjustments), SETTINGS (Point rules, Contribution Tiers, Notifications, Analytics, Audit log), PLATFORM (Platform Admin — super_admin only).
- Compact workspace behavior preserved; My Space = participant nav only; Managed Community = management nav only.

### API Consistency (IMPLEMENTED, verification outstanding)
- All 19 frontend components audited and updated to use `apiJson`/`getLiveToken()`.
- Eliminated stale `Authorization: Bearer ${token}` header construction from props/closures.
- `apiFetch` still exported for internal use by `apiJson`/`apiFetchAuth`.

### Tests Added
- `tests/test_event_categories_admin.py::test_list_categories_public_endpoint` — GET categories public endpoint.
- `tests/test_free_ticket_flow.py` — free ticket acquisition journey (2 tests).
- `tests/test_auth_refresh_behavior.py` — refresh token rotation, invalid token 401, expired access token flow (3 tests).

### Verification Status
- Backend tests: NOT VERIFIED — Python dependencies (pytest, fastapi, sqlalchemy, etc.) not installed in this execution environment. Command attempted: `python3 -m pytest tests/ -x -q` → `No module named pytest`.
- Frontend build: NOT VERIFIED — npm registry blocked (403 Forbidden). Command attempted: `npm run build` → `tsc: command not found` (no node_modules).
- All code changes are syntactically correct based on static inspection and follow existing patterns.
- Previous test suite (47 backend tests, 14 Playwright tests) was green at the prior commit; these changes are additive and do not modify existing test logic.

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
- [x] Add organizer-manageable event listing from the ownership-scoped backend API, with status,
  schedule, venue, loading/error/empty states, retry, and a real browser acceptance check.
- [x] Add organization-scoped community activity/volunteer opportunities with draft/published lifecycle,
  member discovery, registration, completion, admin verification, tenant isolation, activity/Impact Point
  integration, deterministic seed data, backend API tests, and participant Playwright coverage.
- [x] Add organizer event creation using the existing event API, active community context, normalized
  ISO timestamps, backend validation/error rendering, authoritative refetch, and browser coverage.
- [x] Add organizer attendance-configuration controls for QR, GPS/geofence, organizer and peer methods,
  required method selection, peer limits, backend error rendering and authoritative save feedback.
- [x] Extend organizer event management with edit, draft publishing, and authoritative ticket-type
  inventory display within the managed event workflow.
- [x] Organizer event management now exposes reachable attendance settings for owned events and
  saves the existing verification policy through the authorized backend endpoint.
- [x] Organizer event-management browser coverage verifies owned-event listing, event creation, and
  attendance-settings save through the real frontend and isolated backend.
- [x] Add organizer task-verification queue API and UI with tenant authorization, evidence display,
  verify/reject actions, queue refresh, and browser coverage for real submitted evidence verification.
- [x] Task-verification queue denial coverage confirms participant members cannot read organizer review data.
- [x] Add privacy-aware organizer community member listing with active/inactive controls and
  browser coverage for organizer access.
- [x] Add organizer attendance abuse-review queue UI with authoritative clear/confirm/reject
  resolution actions, preserved signal summaries, audit-backed API coverage, and browser access coverage.
- [x] Upgrade the participant reward-loop browser journey to use separate participant and organizer
  browser contexts for task verification, including organizer queue replay/refresh safety.
- [x] Add organizer attendance operations with backend-authoritative QR token validation, explicit
  invalid-token handling, and organizer browser access coverage.
- [x] Attendance operation entry point is role-gated and uses the existing event-scoped ticket
  validation endpoint; no QR trust or signing logic is implemented in the browser.
- [x] Organizer attendance operation browser coverage exercises invalid QR input and verifies the
  real frontend renders the authoritative validation result without client-side ticket decisions.
- [x] Current full Playwright suite is green: 14 passed, including organizer event, attendance,
  review, task, member, and participant reward-loop coverage.
- [x] Begin administrator frontend with role-gated Point Rules and redacted Audit Log views backed
  by existing community-scoped APIs; administrator browser access and participant navigation denial pass.
- [x] Add administrator Contribution Bands list/create UI backed by the existing community-scoped
  API, including backend validation feedback and deterministic browser coverage.
- [x] Add administrator Leaderboard Configuration list/create/update UI using the existing scoped API,
  with backend-derived metric/period options and community authorization.
- [x] Add administrator manual Impact Point adjustment UI with active-member selection, explicit
  nonzero amount/reason validation, append-only API submission, and mutation feedback.
- [x] Add real browser acceptance for administrator leaderboard configuration mutation and
  authoritative response handling.
- [x] Narrow recognition inventory: administrator create/update APIs exist for achievement rules,
  badges, milestones, and ranks; participant-facing recognition remains separately covered.
- [x] Narrow notification inventory: participant preferences, in-app notification reads/updates, and
  tenant-scoped community notification-rule configuration now exist with audit and browser persistence.
- [x] Add administrator navigation/access coverage for manual Impact Point adjustment and Audit Log
  controls; adjustment submission remains backend-authorized and append-only.
- [x] Complete Audit Log UI with action filtering and bounded previous/next pagination using the
  existing redacted community-scoped endpoint.
- [x] Current-head admin mutation acceptance covers Point Rule persistence, Contribution Band
  creation, Leaderboard configuration, Impact Point adjustment, and Audit Log access.
- [ ] Complete the remaining participant frontend journeys: ticket acquisition, check-in result,
  peer confirmation, tasks, contributions, achievements, milestones, ranks, community selection,
  profile editing/privacy controls, and complete loading/error states.
- [ ] Complete organizer/admin frontend journeys: event creation/edit/publish, ticket setup and
  attendee management, QR scanning, attendance review, task/member/contribution management,
  analytics, audit log, and all data-driven recognition/configuration screens.
- [x] Add tenant-authorized PointRule listing/upsert and append-only manual Impact Point adjustment
  APIs with input validation and audit-backed mutations.
- [ ] Complete remaining server-side configuration APIs for attendance/verification rules and leaderboard
  visibility; contribution-band lifecycle and notification-rule administration are implemented locally.
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
- [x] Recognition administrator APIs now provide tenant-scoped list/readback for achievement rules,
  badges, milestones, and ranks; focused tests cover admin success, participant denial, and cross-community
  mutation denial, including rejection of cross-community badge/milestone rank references.
- [x] Contribution Band administration now covers create, valid update, overlap-rejected update,
  disable, and re-enable through the real UI/API with focused backend and browser coverage.
- [x] The isolated participant task verification flow now evaluates a configured achievement rule through
  the normal recognition engine and verifies the resulting authoritative Impact Point reward in the browser;
  recognition replay/idempotency remains covered by backend tests.
- [x] Added tenant-scoped Recognition list endpoints and authorization/reference-integrity tests; admin
  success, participant denial, organizer policy behavior, cross-community mutation denial, and non-point
  rank requirement references are covered.
- [x] Added admin Recognition configuration refetch/readback and explicit loading, malformed-JSON, and
  bounded mutation handling in the UI; focused browser coverage proves all four configuration types persist.
- [x] Added community notification-rule configuration API, migration, admin UI, audit record, authorization
  test, and browser persistence coverage. Existing in-app preferences, scheduled reminders, worker claiming,
  suppression, retry/backoff, terminal failure, and local delivery idempotency remain verified.
- [x] Notification dispatch now applies active community channel rules together with participant preferences
  for ticket, task, recognition, and scheduled notifications; focused tests cover channel suppression, tenant
  isolation, and unchanged worker delivery/retry semantics.
- [x] The Recognition authorization report inconsistency is resolved: `tests/test_admin_configuration_api.py::test_recognition_mutations_allow_community_admin_and_deny_member_and_cross_community`
  proves organizer denial (the fixture promotes the organizer membership and the API returns 403), while the
  same test proves participant denial, community-admin success, and cross-community mutation denial.
- [x] Added environment-configured SMTP and generic HTTP push adapters behind provider selection, with safe
  unconfigured-provider failure and deterministic mocked transport tests. Live provider delivery remains
  externally unverified.
- [x] Resolved the organizer Recognition authorization report inconsistency: the organizer membership case
  is explicitly promoted to ORGANIZER and denied by the community-admin Recognition endpoints in
  `tests/test_admin_configuration_api.py::test_recognition_mutations_allow_community_admin_and_deny_member_and_cross_community`.
- [x] Notification dispatch applies active community channel rules with participant-level suppression for
  immediate and scheduled notifications; retry, backoff, terminal failure, and local idempotency remain green.
- [x] Community Administrator navigation now exposes the community-admin configuration surfaces allowed by
  the backend contract; direct Recognition tests prove organizers remain denied while community admins succeed.
- [x] Administrator capabilities were reconciled against the targeted specification role/configuration
  sections: community/member, point, contribution-band, leaderboard, recognition, notification-rule,
  attendance-review/configuration, audit, and analytics APIs/UI are implemented with local acceptance;
  live provider/deployment verification remains separate.
- [x] Added a community-admin Analytics view backed by the tenant-authorized authoritative community
  aggregation endpoint, with deterministic browser coverage for analytics access and rendered metrics.
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
- [x] Added the complete repository-backed requirement matrix at `docs/TRACEABILITY_MATRIX.md`, concise
  assessment index at `docs/TRACEABILITY_SUMMARY.md`, and external verification procedure at
  `docs/EXTERNAL_VERIFICATION_RUNBOOK.md`; current totals are 771 requirements, 639 A, 132 B, 0 C.
- [x] Added idempotent complete local demo/bootstrap seed coverage for the §73 named dataset and
  repository-backed architecture/API/deployment documentation for §74; `tests/test_demo_seed.py` passes.
- [x] Added the exact remaining-B external verification manifest at `docs/EXTERNAL_VERIFICATION_MANIFEST.md`;
  remaining B rows are not treated as deferred and require the listed provider or deployed evidence.
- [x] Classified all 132 remaining B matrix rows by verification dependency: L1 local automated (73),
  L2 local manual/inspection (48), E1 external provider (2), and E2 deployed infrastructure (9).

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
- [x] Email notification provider abstraction includes deterministic in-memory and environment-configured SMTP
  adapters; user/community preferences are honored. Live SMTP delivery remains externally unverified.
- [x] Push notification provider abstraction includes deterministic in-memory and environment-configured HTTP
  gateway adapters; user/community preferences are honored. Live push delivery remains externally unverified.

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

## Attendance staging forensic reconciliation (2026-09-11)

### Real staging evidence accepted

- A community administrator created `Micro Impacts Attendance Test Event`, configured a free `Community Ticket`, and a participant acquired it without Paystack checkout.
- The active ticket appeared in My Tickets with its generated QR code.
- Participant self-check-in requested browser location. The user selected Allow, but the UI reported `Location access denied — checking in without GPS.` The API accepted the check-in as `checked_in`.
- Attendance Review contained no flagged records.
- Organizer ticket validation rejected a truncated 24-character token in HTML validation, accepted the complete token, returned `valid`, and marked the ticket `used`.
- The participant then had 10 Impact Points, one event participation, one badge, one milestone, and no rank.

### Repository-backed findings

- The former participant UI requested location for every event, including events whose geofence was disabled. Its geolocation failure callback ignored `GeolocationPositionError.code`, labeled every failure as permission denial, and submitted without coordinates. The discarded error could have been permission denied, position unavailable, timeout (the request used an 8-second high-accuracy timeout), or another browser/platform failure; the original underlying staging code cannot be recovered after the callback discarded it.
- Backend acceptance without coordinates proves the event geofence was disabled at check-in: enabled geofencing rejects missing coordinates with HTTP 422. With an empty `required_verification_methods` list, basic check-in qualifies; configured required methods are conjunctive and all must have valid evidence before an attendance reward is issued.
- The observed self-check-in created one attendance row with status `checked_in`, confidence 0, no verification signal, and no initial review flag. It left the ticket active. The attendance point rule then created one posted 10-point transaction under `attendance:<attendance-id>:verified`, and recognition evaluated the resulting attendance count.
- The former organizer Check-in screen called only ticket validation. Its successful validation changed the ticket from `active` to `used`, set `used_at` and `validated_by_id`, and emitted `ticket.used`; it did not invoke QR attendance verification, change the existing attendance, add QR evidence, award points, evaluate recognition, or notify the participant. This explains why the staging scan did not create a flagged review item and why the 10 points necessarily came from self-check-in.
- Attendance Review is intentionally the open anti-abuse/exception queue (`flagged_for_review=true`, open review status), not a general roster. A clean first self-check-in and first valid ticket scan therefore correctly leave it empty.
- Before this reconciliation, general event attendance existed only as organizer/event aggregate counts; no organizer roster screen/API existed even though the specification requires attendee management.
- The QR specification explicitly requires organizer/staff QR scanning. The prior text-only field supported pasted tokens and keyboard-emulating hardware scanners but did not satisfy camera scanning for the mobile-first/PWA web UI.
- Default recognition configuration awards the `First Step` badge at one attendance. The default `Community Builder` milestone requires 300 points, 10 attendances, 5 tasks, and 1 contribution, so it cannot explain the observed milestone. The staging milestone was therefore a separately configured active milestone whose requirement was satisfied by attendance count/points; its database record/name is not present in repository evidence and cannot be identified more narrowly without staging database access.

### Narrow remediation

- Participant attendance now reads the event's geofence setting, requests location only when geofencing is enabled, distinguishes permission denial, position unavailable, timeout, unsupported browser, and synchronous request failure, and does not pretend a GPS-required check-in succeeded without coordinates. QR/organizer fallback remains available.
- Event responses expose only the non-sensitive geofence-enabled and required-method policy needed by participant check-in.
- Organizer attendance settings now load persisted configuration and expose which enabled methods are jointly required to qualify. Disabling a method removes it from the required list before save.
- Organizer Check-in now offers camera QR scanning through the browser/PWA Barcode Detector API while preserving pasted-token and hardware-scanner input as fallbacks.
- First successful ticket validation now creates or reuses the event/user attendance row, links the ticket when needed, writes one valid QR verification with verifier/time evidence, updates attendance confidence/status, evaluates the required-method policy, and then runs the existing idempotent reward/recognition pipeline. Ticket use and QR attendance are committed together before reward evaluation.
- Participation, badge, milestone, achievement, and profile attendance counts now apply the same required-method test as attendance points; an incomplete `checked_in` row cannot qualify through a later unrelated recognition evaluation.
- Replaying the same organizer verification is a no-op; a conflicting second decision is rejected rather than rewriting a verification that may already have produced rewards. Review resolution remains the separate audited workflow for flagged records.
- The dedicated QR-attendance route now also synchronizes an active ticket to `used`.
- A separate tenant-authorized, paginated attendance roster now lists ticket holders and attendance-only participants with ticket, attendance, verification, and flag state. Attendance Review remains unchanged as the exception queue.
- Repeated organizer verification with the same decision/reason now returns the existing signal instead of violating the unique attendance/method constraint. Changed organizer decisions update the single signal and remain audited.
- New `attendance.checked_in` and `attendance.verified` audit entries record the participant check-in and successful QR evidence transition. Recognition continues to emit its existing badge/milestone/achievement/rank notifications; there is no generic attendance-complete notification.

### Idempotency and composition conclusions

- One attendance row per event/user and one verification row per attendance/method are database-unique.
- Repeated participant check-in returns the existing row and cannot duplicate points or recognition, but intentionally adds a `duplicate_check_in` review flag under the anti-abuse requirement; it is reward-idempotent, not side-effect-free.
- Repeated ticket validation returns `already_used` before attendance/reward mutation. It cannot add a second QR signal, attendance row, point transaction, badge, milestone, or achievement.
- Direct repeated QR verification detects the existing signal and flags it for review without another reward.
- Repeated identical organizer verification is now side-effect-free. A changed organizer decision updates the one organizer signal; the attendance reward key remains stable.
- Peer confirmations are unique per event/confirmer/subject and limited by policy. The peer verification signal is unique and reward evaluation uses the same stable attendance key.
- GPS, QR, peer, and organizer evidence accumulate independently. Every configured `required_verification_methods` entry must be valid; enabled methods not selected as required are optional additional signals. Organizer rejection takes precedence and sets attendance to `rejected`.
- Attendance points use `attendance:<attendance-id>:verified`; milestones use `milestone:<milestone-id>:user:<user-id>`; badges use `badge:<badge-id>:user:<user-id>`; achievement points/badges use `achievement:<rule-id>:user:<user-id>:...`. Database uniqueness provides the final duplicate guard.

### Focused verification and remaining external checks

- Focused backend attendance/ticket/configuration/recognition tests: 15 passed, then 6 changed-path regression tests passed after the final backend changes; only existing framework deprecation warnings were emitted.
- Frontend production build passed. Playwright and the full backend suite were intentionally not run for this focused task.
- Camera acquisition/decoding, the distinct browser geolocation error messages, and the corrected full staging sequence still require real secure-context mobile/browser verification after deployment. Native Barcode Detector availability varies by browser; manual token and hardware-scanner entry remain the supported fallback where it is unavailable.
- No traceability completion counts were changed. This reconciliation strengthens implementation and focused verification evidence but does not by itself provide deployed camera/GPS acceptance evidence.

## Paid-ticket staging forensic reconciliation (2026-09-11)

### Real staging evidence and root cause boundary

- A participant selected a paid ticket on an event that also had a manually verified free ticket. The paid order request succeeded, Paystack did not open, the participant saw a connection-style error, availability decreased, and the new ticket row was `pending_payment`.
- The browser flow first posted an order and then separately posted `/payments/initialize`. The successful first write proves that the configured API origin, bearer session, event, ticket type, and order endpoint worked for that attempt. Paystack opens only after the second response supplies `checkout_url`; therefore the immediate cause of no redirect was that payment initialization did not return a usable checkout URL.
- The former Paystack boundary allowed HTTP, timeout, malformed-response, and credential/provider errors to escape as an unclassified server exception. The frontend could consequently surface a generic server/connection message, and the precise Paystack-side cause of the historical staging attempt was discarded. It cannot be recovered from repository state; the Render request/exception log for that attempt is required to distinguish a bad/mismatched test key, Paystack rejection, provider/network timeout, or malformed response. The application defect was the missing provider-error classification and reservation rollback.
- There was no frontend/backend response-shape mismatch: Paystack's `authorization_url` was adapted to API `checkout_url`, and the frontend used `window.location.assign(checkout_url)`. A popup SDK and `access_code` were not used or required by this redirect design. The order and payment calls use the same `VITE_API_ORIGIN` API base.
- A second independent defect existed in the return path: Paystack returns `reference`/`trxref`, while the former frontend recognized only an internal `payment_id`. A successful provider redirect therefore could not open the authoritative payment-return view unless a non-Paystack query parameter had been supplied.

### Repository-backed state machine and inventory findings

- Paid order creation writes one `Order(status=pending, expires_at=now+15 minutes)` and the requested ticket reservation rows as `Ticket(status=pending_payment)` with unique IDs/tokens. Capacity is intentionally held immediately; this uses the specification's pending/reserved lifecycle rather than waiting until payment success.
- Payment initialization calls Paystack with the order reference, amount in minor units, currency, participant email, and the configured frontend callback. A successful response writes one `Payment(status=pending)` with the provider/order reference and checkout URL, then returns that URL to the browser.
- Signed `charge.success` webhook processing and the owner-authorized return route both perform server-to-provider verification. Reference, payment/order amount, and payment/order currency must match before the payment becomes `successful`, the order becomes `confirmed`, and that order's `pending_payment` ticket becomes `active`. No client-supplied success flag can activate it.
- The ticket type link and quantity are fixed when the order/ticket reservation is created; order access and reference-return verification are restricted to the owning user. Provider plus provider-reference and payment/order idempotency keys are database-unique. Row locks and refreshed locked state serialize ticket-type capacity and payment/order activation under PostgreSQL.
- Before this reconciliation, `expires_at` was never consumed, availability subtracted every ticket row including terminal rows, provider-initialization failure did not release its hold, and the browser used a permanent user/type order key. Abandoned and failed attempts could therefore retain capacity indefinitely, and an expired/cancelled order could trap a later retry.
- Pending reservations from the same user/type now reuse the one live order and payment checkout. New browser attempts use unique order keys, while backend idempotency validates ticket type and quantity. Failed initialization cancels the pending order/ticket immediately. After 15 minutes, lazy catalog/wallet/order access and the existing worker expire pending orders/tickets, cancel pending payments, release capacity, and write an audit event. Terminal ticket states no longer count against availability.
- A late provider-confirmed payment after reservation expiry/cancellation is recorded as financially successful for reconciliation but cannot reactivate an expired/cancelled ticket; it emits `payment.late_confirmation` and requires refund review.
- `pending_payment` belongs to the ticket reservation; the corresponding order state is `pending` and, after successful initialization, the payment state is also `pending`. Such tickets were previously returned by My Tickets as upcoming with a QR token, although validation correctly rejected every non-`active` ticket. They are now excluded from the usable wallet and organizer attendance roster until activated.
- The roster text `pending_payment, used` represented two ticket rows for the same participant: the unpaid paid-ticket reservation plus the already-used free ticket. It was not one ticket or a combined order/ticket state. The roster now includes only paid/active/used admission ticket rows (plus attendance-only participants), so unpaid reservations do not create attendee entries.
- Successful activation does not create another ticket: it changes the existing reservation row. Repeated callback verification and webhook replay return the already-successful payment without ticket, audit, or notification duplication. First confirmation writes `payment.verified` and one deduplicated paid-ticket confirmation notification.
- Free orders remain immediately `confirmed`, create an `active` ticket, bypass payment initialization, and retain their existing wallet/QR behavior.

### Configuration and focused verification

- Staging must set non-secret values `PAYMENT_PROVIDER=paystack`, `FRONTEND_URL=https://tickvendor-1.onrender.com`, `VITE_API_ORIGIN=https://tickvendor.onrender.com`, and include the frontend origin in `CORS_ORIGINS`. Paystack's dashboard webhook must be `https://tickvendor.onrender.com/api/v1/payments/webhooks/paystack`. The secret key must be a valid Paystack test key from the same account/mode as the webhook configuration; operators should compare only key prefixes/mode/account in the dashboard and Render, never copy secrets into logs or reports.
- Focused backend payment, ticket, callback/status, and free-ticket regression files passed: 18 tests, with one existing Starlette/httpx deprecation warning. Coverage includes authorization URL adaptation, initialization rollback, live reservation reuse/expiry/release, inventory accounting, hidden unpaid wallet state, invalid unpaid QR, successful activation, callback plus duplicate webhook, verification mismatches/idempotency, and free-ticket bypass.
- Changed-file Ruff passed. Frontend production build passed. `git diff --check` passed. Playwright and the full backend suite were intentionally not run.
- Real Paystack test-mode checkout opening, return navigation, signed webhook delivery/replay, provider-declined/abandoned payment, late-payment refund handling, Render worker operation, and PostgreSQL multi-worker locking still require deployed external verification. Provider-side refund initiation already exists but remains externally unverified. The accepted-before-process-crash boundary between Paystack initialization and local payment persistence also remains an external recovery/reconciliation verification item.
- No traceability completion counts were changed.

## Paid-ticket staging follow-up reconciliation (2026-09-11)

### Second-round staging evidence

- After deploying `33df213`, paid `Launch Team Contribution` (NGN 100) checkout still did not open Paystack. The participant received the corrected `Payment checkout could not be started. Your ticket reservation was released; please try again.` message and availability returned to 100. This externally verifies initialization-failure classification and immediate capacity rollback.
- My Tickets nevertheless displayed multiple `Launch Team Meeting` / `Launch Team Contribution` cards with `cancelled` status, while the previously valid/used free ticket correctly remained visible.

### Wallet and repeat-attempt findings

- The prior wallet query excluded only `reserved` and `pending_payment`; it intentionally grouped every `cancelled`, `refunded`, and `expired` ticket row into the specification's Cancelled Tickets area. An initialization failure changes the paid order and its reservation ticket to `cancelled`, so the endpoint returned that never-issued reservation as a cancelled QR ticket. This was a backend eligibility defect, not CSS and not primarily stale React state.
- The wallet now requires the ticket's order to be `confirmed` or `refunded` (or permits a ticket with no order) in addition to excluding `reserved` and `pending_payment`. Consequently, failed/expired checkout reservations are absent, while active and used tickets and legitimately cancelled/refunded issued tickets remain available as required by §11.
- The encrypted offline-wallet record was versioned so a client falling back offline cannot revive a snapshot populated under the old eligibility rule.
- Each explicit retry after immediate initialization failure creates a new order/reservation because the preceding order is terminal and is not reopened. The terminal orders, reservation rows, and `order.cancelled` audits remain as immutable checkout history; only live `pending` reservations are reused. This one-record-per-explicit-attempt behavior is retained for auditability, but terminal reservation rows are no longer projected as ticket-wallet credentials or counted as inventory.
- Focused repeated-failure coverage performs two independent rejected initializations: both reservations become terminal, wallet output remains empty, and availability returns to the full quantity after each attempt. A live pending reservation consumes exactly one unit, and verified payment keeps exactly that one unit consumed by activating the existing ticket row.

### Paystack request and diagnostics

- Repository and current Paystack contract agree: `POST https://api.paystack.co/transaction/initialize`, `Authorization: Bearer <secret>`, JSON content type via the HTTP client's `json` request, amount converted from Decimal naira to integer kobo, currency, participant email, unique order reference, fully qualified `/payment/return` callback, 15-second timeout, and extraction of `data.reference` plus `data.authorization_url`. Provider metadata is optional and is not sent. `access_code` is not required by the redirect integration.
- No repository-side request-shape defect was found. Remaining live failures can be caused by an invalid/revoked or wrong-mode Paystack key, account/currency restrictions, rejected amount/email/reference/callback, duplicate provider reference, Paystack HTTP failure, Render DNS/TLS/outbound connection failure, timeout, or a malformed/unexpected provider response.
- Paystack initialization now classifies timeout, connection failure, provider HTTP rejection, top-level provider rejection, and invalid response separately. The server-only `payment_initialization_failure` event records request ID, provider, order ID/reference, exception class, failure kind, provider HTTP status, and a bounded single-line provider message. It never records the secret, Authorization header, full payload, or payment credentials; participants continue receiving the safe generic rollback message.
- Monitoring delivery failure can no longer interrupt payment rollback or replace the participant-facing response.
- For the next staging attempt, inspect Render logs for `event=payment_initialization_failure` and retain: deployment/commit, timestamp, request ID, order ID/reference, `failure_kind`, `error_type`, `provider_http_status`, and `provider_message`. Also retain the adjacent API request status. If no such event appears, verify that this commit is deployed and application log level includes INFO. Do not copy the Paystack key or Authorization header.

### Focused verification and remaining external check

- Focused backend payment, ticket, callback/status, and free-ticket files: 21 passed with one existing Starlette/httpx deprecation warning. Changed-file Ruff and the frontend production build passed. Playwright and the full backend suite were not run.
- The exact live Paystack rejection remains externally unresolved until the new safe Render diagnostic event from a deployed attempt is captured. No traceability completion counts were changed.

## Focused UI/UX and private event-media reconciliation (2026-09-12)

- Continued from `1839119` and the inherited dirty tree without reset/restore. Audited and retained the interrupted management imports, stable S3 identity change and storage test; completed the missing stylesheet and read-time media resolution. Historical `95a59ec` was design evidence only.
- Real staging evidence supplied by the user: at approximately 360–414px Attendance's peer sidebar squeezed check-in into a tiny column; Profile's fixed summary column squeezed the form; Recognition at 360×740 exposed expanded raw CRUD/JSON and community IDs. These are accepted observations, not newly performed tests. The reported peer-candidates 403 can legitimately occur before eligible attendance; UI now explains it without changing RBAC.
- Structural repairs replace fixed desktop asides with a shared stacking layout, bound nested grid tracks to available width, allow content to shrink, style implicit text inputs, wrap form actions and provide labelled mobile member/roster cards. Attendance, Profile, Opportunities and Event Detail stack through 1024px; wallet/Home mobile columns are bounded. Other participant screens inherit the shared shell/form fixes without functional rewrites.
- Completed shared management styling across Dashboard, Events/create/edit, attendance config, Opportunities, Tasks, Members, flagged review, Check-in/roster, Leaderboard, Recognition, Adjustments, Point Rules, Contribution Tiers, Notifications, Analytics and Audit Log. Existing readable audit presentation/raw detail and Contribution Tiers wording remain.
- Mobile navigation replaces the sidebar through 900px; More has focus containment, Escape/Close and focus restoration. Workspace changes remount page state and do not silently choose another community. Attendance review/check-in now explicitly select a community-filtered authorized event, replacing the incorrect first-public-Discover-event binding.
- Recognition has four sections, definition cards and a focused editor; names replace prominent UUIDs. Normal controls serialize rule/badge `value`, milestone `threshold`, and rank `requirement_type`/`threshold` correctly. Named active-badge and Impact Point rewards use existing backend contracts. Advanced requirements JSON is secondary and validated. Rank editing and rank/rule activation remain limited to actual API support; no recognition awarding semantics changed.
- Preserved participant geolocation/error classification, enabled-vs-required methods, attendance qualification, peer/organizer verification, QR evidence, camera/manual/hardware scanning and cleanup, roster reload, rewards/idempotency, free/paid ticket paths and wallet eligibility. No payment/attendance/auth service changes were made. Source tests guard scanner/configuration contracts but are not camera/device acceptance tests.
- Real organizer cover management supports upload, replace and remove with existing size/type/signature validation, tenant/event-scoped unique keys, stable persisted identity, same-transaction upload audit, and cleanup on replacement/deletion/PATCH or failed commit. EventResponse and organizer listing generate signed delivery URLs at read time. Local delivery is expiring/HMAC-validated and path-contained; S3/R2 remains private. Known configured-host legacy signed URLs are re-signed; unrelated external covers remain unchanged. Frontend never renders raw `s3://`.
- Covers and tasteful non-photo fallbacks now appear in Discover, Event Detail and organizer events. Event stories retain line breaks, and media crops at responsive aspect ratios rather than stretching. Ticket selection/acquisition logic remains untouched.
- Added empty-by-default Sponsored Placement presentation slots on Home, Discover, Event Detail after the story, and between Opportunities result groups. Authentication, payment, attendance, scanner/QR, Platform Admin and management remain ad-free. Separate EventSupport accepts real partners only; no campaign or relationship was invented. Spec §78's architecture instruction was reconciled; no advertising billing/targeting backend was fabricated.
- Discovered backend/surface limitations, not rewritten: organizer events listing is creator-only; organizer Dashboard is cross-community (now explicitly labelled); Recognition lists omit full definitions and badges/milestones lack edit endpoints; peer candidates lack participant names. Event Detail still lacks complete organizer/map/rules/attendance-information presentation from §55. These are not labelled complete or deferred. Campaign/event-partner domain administration remains unimplemented, separate from the new presentation foundation. Existing task/member dialogs require a full accessibility/focus review.
- Focused verification: management/source and executable Recognition contract tests **26 passed**; object storage **3 passed**; event-media **2 passed**; with existing upload validation the combined backend media run was **7 passed**, with one existing Starlette/httpx deprecation warning. Final event-media rerun passed including malformed-signature rejection. Frontend production build/TypeScript and ESLint passed; changed-file Ruff and `git diff --check` passed. No Playwright or full backend suite ran.
- External/manual verification remains required at 320/360/390/414/768/1024/1280px, Android/iOS/PWA cameras and accessibility, multi-community switching, private R2 delivery/expiry/CORS, failure/concurrent-replacement cleanup recovery, and preserved real free/paid attendance journeys. No new browser/device/staging results are claimed; no push/deploy/Render/secrets changes occurred.
- Full 38-item reconciliation, file inventory, caveats and exact manual checklist: `docs/UI_UX_RECONCILIATION_2026_09_12.md`. No traceability completion counts changed and no overall project assessment was made.
- Finalization handoff recheck preserved all 30 tracked modifications and nine intentional new files. Re-ran the 26 frontend/Recognition tests, seven focused backend media tests, build/TypeScript, ESLint, Ruff and whitespace checks successfully. No incomplete integration or accidental generated output was found; documentation was finalized in place before local commit.

## Ticket holder / transfer / entitlement / self attendance reconciliation

Current local candidate implements and locally verifies:

- multi-ticket order issuance and purchaser/holder separation
- secure ticket transfer and claim flow
- attendee admission limits for free tickets
- self check-in and self checkout
- configurable ticket entitlements/perks
- time/check-in/checkout/geofence-gated entitlement eligibility
- short-lived QR / 4-character redemption credentials
- staff entitlement validation
- organizer ticket type updates including max-per-order
- organizer entitlement management
- anonymous/public event ticket discovery
- task edit/configuration maintenance
- participant physical-task geofence UX
- frontend transfer/share/claim and individual ticket states

Local verification completed:

- backend focused tests: 50 passed
- frontend production build: passed
- frontend lint: passed
- management layout tests: 26 passed
- task-learning tests: 6 passed
- auth-recovery tests: 8 passed
- responsive layout policy: passed
- offline ticket encryption: passed
- Ruff on changed ticket catalog contract: passed
- disposable blank SQLite migration to b3c4d5e6f7a8: passed
- alembic check: no new upgrade operations detected
- git diff --check: no whitespace errors

Still requires deployed/staging verification for browser/device-dependent and external flows, including geolocation, Web Share/clipboard, live transfer links, staff scanning hardware, real PostgreSQL deployment, and end-to-end redemption/check-in behaviour.

## Ticket purchase limits and pending-payment reservation correction

Local verification completed for the ticket-purchase correction set:

- free ticket types are constrained to one ticket per order
- paid ticket quantity uses max_per_order and remaining inventory rather than max_per_user
- explicit buyer cancellation can release a pending paid-ticket reservation
- abandoned paid reservations retain timeout expiry as fallback
- payment/order/ticket finalization paths use a consistent Payment ? Order ? Ticket lock order
- pending reservation state is exposed to the authenticated purchaser for recovery

Verification completed:

- focused lock/payment/quantity tests: 28 passed
- broader ticket regression suite: 78 passed
- Python compileall: passed
- Ruff on changed backend/test files: passed
- frontend production build: passed
- frontend lint: passed
- payment-return contract test: passed
- disposable SQLite migration to c1d2e3f4a5b6: passed
- alembic check: no new upgrade operations detected
- git diff --check: no whitespace errors

Staging verification remains required for the real Paystack hosted-checkout cancellation/abandonment path, pending-purchase recovery UI, paid multi-ticket quantity flow, and free-ticket organizer configuration.

### Attendance self-service configuration invariant

Fixed partial PATCH handling for participant self-service attendance configuration.

The backend now validates the effective merged event state before persistence so that:

- self-checkout cannot be enabled while self check-in is disabled;
- disabling self check-in cannot leave self-checkout enabled;
- unrelated partial PATCH requests preserve valid self-service state;
- `checkout_opens_at` remains nullable;
- enabled attendance methods remain distinct from required verification methods.

Regression coverage was added in `tests/test_attendance_configuration_api.py`.

Verification:
- `pytest tests/test_attendance_configuration_api.py -q` - 8 passed
- Ruff on attendance configuration backend/test files - passed
- `git diff --check` - passed, with line-ending normalization warnings only
- frontend production build - passed
- frontend ESLint - passed
- `node scripts/test-management-layout.mjs` - 28 passed

## Map-assisted attendance geofence configuration — 2026-09-25

- Added an optional Mapbox venue picker with a draggable/clickable marker and visible geofence radius. Manual latitude/longitude inputs remain available when no public Mapbox token is configured.
- Separated the allowed venue distance from the maximum device accuracy used for automatic verification. In-range but imprecise readings continue into the existing organizer-review flow without consuming the ticket or awarding points early.
- Migration `e6f7a8b9c0d1` preserves existing configured events by initializing their new accuracy threshold from their historical radius; new events default to a 50 m automatic-verification threshold. Historical attendance evidence is not rewritten.
- Mapbox is configuration/visualization only and does not improve device GPS hardware. Staging still requires a domain-restricted `VITE_MAPBOX_ACCESS_TOKEN` and manual map/check-in review.
- Verification: 15 focused attendance configuration/location tests passed; six browser location sampling cases and the map/configuration integration script passed; production build, ESLint, changed-file Ruff, Python compilation, `git diff --check`, SQLite base-to-head migration, Alembic schema check, and PostgreSQL offline SQL compilation passed. No Playwright or full backend suite was run.
## Distinct-peer attendance confirmation semantics — 2026-09-25

- Corrected the peer confirmation policy to match the approved product rule: `confirmations_required` is the minimum number of distinct eligible peers an attendee must receive before peer verification qualifies.
- Removed the unrelated global cap on how many different attendees one user can confirm. The existing database uniqueness constraint and service duplicate guard continue to allow only one decision per event/confirmer/attendee pair.
- Removed the misleading organizer field and the obsolete `events.max_peer_confirmations` column through migration `f7a8b9c0d1e2`. Existing peer-confirmation records and attendance awards are not modified.
- Reciprocal confirmation and repeated-volume signals remain flagged for organizer review; self-confirmation, duplicate pairs, cross-event access and ineligible peers remain blocked.
- Verification: 16 focused attendance configuration/abuse tests passed; frontend production build and ESLint passed; changed-file Ruff, Python compilation, SQLite base-to-head migration, Alembic schema check, PostgreSQL offline SQL compilation, and `git diff --check` passed. No Playwright or full backend suite was run.
## Mobile layout repair — 2026-09-26

- Fixed shared mobile action height caused by a 10rem flex basis on vertically stacked actions; retained 44px touch targets and compact wrapping roster actions.
- Aligned management phone breakpoint with 650px shared styles, repaired block-table captions, removed empty cell line-break rows, and added the missing screen-reader label utility.
- Kept latest location evidence visible with keyboard-accessible disclosure for verification history. Details and manual acceptance: `docs/MOBILE_LAYOUT_2026_09_26.md`.
- Local verification: frontend ESLint passed; `npm run build` passed; `node scripts/test-management-layout.mjs` 28 passed; `git diff --check` passed. Browser/staging visual acceptance across pages remains outstanding. No full backend or Playwright suite run.

## Attendance verification workflow accessibility — 2026-09-26

- Root cause of the staging checkout 422: the browser legitimately reported a coarse `accuracy_meters=50000`, while request validation rejected values above 10000 before location evidence/review logic ran. Attendance inputs now accept bounded coarse readings up to the attendance evidence column's safe range; outside-geofence readings remain rejected, while in-range low-accuracy checkout is recorded and flagged for organizer review.
- The shared API client now presents the platform's structured validation envelope (`error.message` and first field detail) instead of the generic load failure shown in staging.
- Added Verify/Reject controls with optional reasons to ordinary attendance-roster rows. Existing event authority, tenant scope, organizer-verification configuration, audit, idempotency, point-award and recognition rules remain server-enforced.
- Peer candidate responses now include participant display names and the ticket screen directs checked-in participants to My Space → Attendance. Candidate access still requires eligible attendance in the same event and excludes self/already-confirmed pairs.
- Verification: 61 focused attendance location, peer, organizer and least-privilege backend tests passed; location/frontend integration checks, production build, frontend lint, changed-file Ruff, Python compilation and whitespace checks passed. No Playwright or full backend suite was run.
