# Task staging reconciliation — 2026-09-13

## Scope and authority

Continued the intentional working tree based on `6c345166065e7cfd11aab4ee33272b2534a3d5eb`.
The authoritative contract remains `TICKVENDOR_SPEC.md`. No specification text, historical
completion counts, overall percentage, payment/provider configuration or deployment was changed.

Sections 19, 22–23, 25–28, 39, 48, 50, 52 and 62 support configured task rewards/evidence,
idempotent awards, recognition, isolation, resilient requests, accessibility and useful errors.
Embedded quizzes, embedded opinion-neutral surveys, video attention checkpoints and a separate
platform-wide ceiling hierarchy are **requested compatible product extensions**, not newly
discovered requirements in the original specification. Existing survey-link tasks remain valid.
No course/LMS, DRM, YouTube identity access or guaranteed watch-verification claim was added.

## Real staging evidence and repository causes

The user actually created, assigned, submitted and reviewed a video task and a physical task.
The configured YouTube link worked. A missing active task-completion rule initially blocked
verification. After a 5-point rule was configured, the two verified tasks changed the participant's
points from 10 to 15 to 20 and task count from 0 to 1 to 2, despite cards advertising 20 and 10.
Suspension/restoration worked; suspended login incorrectly said invalid credentials. A transient
task-create request failed; values survived in the mounted form but were not refresh-persistent.
Administrators had to find newly revealed forms manually; display-name-only assignment was ambiguous.
Home sometimes loaded slowly. These are supplied manual observations, not tests run by this agent.

| Finding | Repository-backed cause and disposition |
|---|---|
| Advertised reward differed from award | Task reward was only a nonzero eligibility switch; `award_points` selected a PointRule amount. Display now uses effective policy; old tasks retain rule-based semantics, new tasks carry explicit bounded amounts. |
| Missing-rule 409 | Expected positive-reward verification precondition; retained. New creation guidance permits zero-point tasks and prevents unsupported positive promises. |
| Rule precedence | DESC on nullable community ID selects NULL first on PostgreSQL. Explicit CASE now selects the active community rule before the global fallback. |
| Apparently conflicting rules | Different source types are distinct, not duplicates. Community/source already has a unique constraint. Active global/source lacked equivalent NULL-safe uniqueness; migration and ORM add it. |
| Suspended login | `is_active` was included in the generic credential-failure branch before password validation. Valid password now precedes a suspended-account 403; wrong/unknown credentials remain generic 401. |
| Moderation reason privacy | Existing moderation reasons are not classified public versus internal. They are deliberately not returned at login. |
| Physical evidence labels | Frontend already used configured evidence types, not physical type. Backend's `required_evidence_types or ['text']` wrongly treated an explicit empty list as text-required. Empty now really means no required text/URL/attachment. |
| Lost drafts | Form state was component-only. Reusable encrypted browser drafts now cover creation and participant evidence. |
| Result visibility | Revealed sections had no consistent focus/viewport handling. Shared focus helper and native dialogs now cover changed task/event/recognition/governance actions. |
| Generic notifications | Service emitted generic text and verification schema discarded the UI's rejection reason. Notifications now name task, actual posted points and participant-visible revision reason. |
| Duplicate queue rows | Review joined all submissions after resubmission. It now selects only the latest submission per pending assignment. |
| Home delay | Three requests were already parallel. No evidence proves a waterfall, internet fault or Render cold start. Added a 20-second UI deadline, abort/cleanup and retry, including a pending refresh boundary. |

## Reward governance and historical compatibility

`PointCeiling(source_type, maximum_points)` is platform-global, unique and nonnegative.
Only Super Admin can PUT a ceiling; authenticated users may read guidance. Changes require
a meaningful reason and append an audit. Community Admin maintains its one community/source
PointRule through the existing authorized endpoint. A positive community rule requires a
configured ceiling and must not exceed it. Negative automatic rules are rejected; authorized
manual corrections remain a separate, audited adjustment path, not automatic task rewards.

For task completion:

1. Select active community rule, otherwise active global fallback.
2. Effective community amount = nonnegative rule amount limited by the configured platform ceiling.
3. New task creation requires a ceiling for a positive reward and rejects a reward above that amount.
4. **New `explicit` task:** eventual award = minimum of stored task reward, current effective
   community amount and platform ceiling. A zero-reward task stays zero.
5. **Existing `legacy_rule` task:** a nonzero old reward remains an eligibility switch; award is the
   effective rule amount, not the old advertised number. Zero remains zero. Thus an old 20-point
   card with a 5-point community rule still awards 5, not 20.
6. Removing the active rule still blocks positive-reward verification with 409. It does not silently
   finalize the task with a zero transaction. Lowering a configured rule/ceiling affects later awards,
   not posted history. Task card values are current eligibility guidance, not a historical ledger.

`award_points` applies any configured source ceiling even to explicit override amounts. Existing
unconfigured non-task reward sources retain their previous behavior; no universal arbitrary cap was
invented. New positive community rules cannot introduce uncapped sources. Existing posted transaction
lookups return before current-policy evaluation. Rule changes never recalculate those transactions.
Ceiling reads use PostgreSQL shared row locks, coordinating in-flight awards with ceiling updates;
creation races are rejected by source uniqueness. Live PostgreSQL race verification remains outstanding.

Migration ceilings are derived from **MAX(existing PointRule.points), clamped at zero**, for each
already represented source, including historical rules. There is no hardcoded 20-point platform default.
Super Admin must configure ceilings for new positive sources. This is a conservative compatibility
initialization, not a claim that historical maxima were originally platform policy.

## Task transitions, evidence and idempotency

- Create: organizer authority, tenant/event checks, reward/config validation, explicit reward mode,
  task-created audit. Assignment requires active community membership; repeats return the existing
  assignment under a task-row lock and its existing unique assignee constraint.
- Accept/start: owned assignment, available task/community and active membership; existing legal
  transition rules are preserved. These transitions do not award points.
- Submit: lock/reload assignment, check owner/membership/availability, compare any replay key against
  the complete evidence/answers payload, enforce due date and configured evidence, then grade server-side.
  Failed assessment becomes rejected, successful work becomes submitted if organizer review is required,
  otherwise verified. Persist submission, grade, attempt number and audit. A new attempt after due date
  is rejected, including a previously rejected assessment; retry keys can recover an already accepted request.
- Organizer approval: only a submitted assignment can advance to verified. A rejected assessment cannot
  bypass grading through this endpoint. Approval posts the effective award, audit and notification in one
  primary transaction. Rejection persists its participant-visible reason and notifies; revised evidence can
  be submitted subject to attempt/deadline rules. Review exposes the latest evidence, not duplicate rows.
- Automatic verification uses the same award key and actual-point notification as organizer verification.
  Repeated approve of verified / reject of rejected is a no-op for primary side effects.
- Award key: `task:{assignment_id}:verified`, protected by the ledger's database uniqueness.
  Submission keys are unique, payload-checked, and persisted by the participant draft before sending.
  Unkeyed repeated successful submission is rejected by assignment state, not treated as new work.
- Award inserts use a savepoint so a uniqueness collision does not invalidate a caller-owned transaction.
  Recognition runs after primary commit. A keyed submission replay or repeated approval retries recognition
  after a post-commit failure without duplicating the task transaction or verified notification.
- Verified notification deduplication uses the same stable assignment reference. Repeated rejection does
  not create another notification; rejection of a genuinely revised submission is a new decision.

## Requested learning extensions

**Video checkpoints:** optional bounded configuration (up to 20), position label, participant prompt,
server-only expected code, all or N-of-M threshold, case policy and 1–20 attempts. The UI authors
case-insensitive checks; API configuration also supports case sensitivity. No randomized subset policy
was introduced. Codes are attention evidence and may be shared, not proof of full video viewing.
Ordinary video tasks and exact external URLs remain supported with safe new-tab links.

**Quiz:** a proper task type, up to 30 objective single/multiple-choice questions, bounded choices,
equal question weight, passing percentage and attempt limit. Subjective automatic grading is rejected.
Correct-answer indexes remain server-side. Score/pass/attempts remaining persist in submissions and
are available through owned attempt history and the participant task list. Organizer review, if enabled,
remains additional to passing; it does not replace grading.

**Survey:** the existing survey type now optionally embeds single/multiple-choice, 1–5 rating, short-text
and long-text questions. External survey links remain compatible. Configuring preferred/correct answers
is rejected; valid completion, independent of opinion, enters the normal task verification/reward path.
Private answers are returned only to the authorized community organizer review queue, not shared task lists.

Participant list/detail serializers strip checkpoint expected answers and quiz correct answers. The
management configuration response requires organizer authority. Attempt history requires ownership.
Assessment results expose scores, not answer keys. Required physical text, URL and attachment evidence
is independent of task type; organizer-only review with no required evidence is supported. No new
automatic attendance-to-task verification coupling was invented.

## Recognition, notifications, governance and performance

`recognition.user_metrics` sums posted ImpactTransactions and counts verified assignments, not card
values. Existing badge/milestone/achievement/rank evaluation and award references remain unchanged.
Profile/global progress, community analytics and leaderboard inputs are authoritative transactions.
Recognition definitions remain community-scoped; participant Home aggregates legitimate community
earnings and earned recognition. No separate cross-community rank system was introduced or claimed.
Actual badge/milestone names from the user's later task journey cannot be inferred without staging data.

Task notifications report actual posted task points (zero if the task has no award), task title and
revision reason. Existing preference/delivery/outbox behavior is reused. Configuration, task creation,
assignment, submission and verification/rejection are audited; answer keys are not copied to audits.

Previously committed Super Admin administrator assignment/demotion, reversible moderation,
membership discovery/access/invite/accept/decline/request/approve/reject/withdraw/leave, and owned
archive/history controls remain intact. The specification does not establish a minimum local Admin
count: explicit Super Admin final-Admin removal retains its warning and platform oversight semantics.
No ordinary Admin escalation or hard deletion of participation/financial evidence was added.

Assignment selection searches display name/username and already-authorized record identifier, with
private-profile redaction retained. No email was newly exposed. The existing member-list endpoint
returns all non-left members; search is client-side, not a claimed new server-paginated directory.
Its large-community performance remains an external/load-test concern.

Home still uses three parallel requests. New policy calculation avoids per-task rule/cap queries by
reusing policy per community in task lists/details. No speculative backend cache, cold-start fix, or
measured staging latency improvement is claimed. Home explicitly offers retry after failure/deadline.

## Draft and focus boundaries

Drafts use AES-GCM encrypted IndexedDB records with non-exportable browser keys, scoped by authenticated
user, community, form and task entity. Tokens/passwords/payment credentials are not copied into drafts.
Different scopes cannot hydrate each other. Same-origin XSS or a person controlling browser developer
tools is not defeated by this storage model. Storage-denial/recovery errors are visible.
Writes are serialized; unload during pending writes warns; evidence replay keys flush before requests.
Failures preserve entered values. Only success or explicit confirmed discard removes a stored draft;
closing participant evidence retains it. Drafts never patch newer server entities, and server state,
membership, due dates and attempt rules still govern recovered submissions.

The shared helper focuses a revealed control/section without scrolling if already visible, otherwise
brings it into view. Task assignment/evidence use native modal dialogs with Escape and focus restoration.
Task evidence and rejection panels have distinct targets; event/recognition editors and governance
inspection reuse the helper. Existing responsive shell and scanner/payment/attendance UI were not redesigned.

## Migration and recovery

Revision `c8d9e0f12345` follows staging head `b7c8d9e0f123` and remains the only Alembic head.
It adds legacy reward mode, submission answers/results/replay key, source ceilings and matching ORM
constraints/indexes. Duplicate active global rules retain their rows; only the most recently updated
(ID tie-break) stays active. No task/evidence/Impact transaction is deleted or recalculated.
The governance migration test now targets its own revision rather than asserting it remains HEAD forever;
the new migration test independently asserts the exact new head.

Isolated populated SQLite upgrade verifies old task amount/mode, evidence text and posted 5-point
transaction, ceiling derivation, duplicate-global deactivation and unique index; downgrade/re-upgrade
is exercised only on that disposable database. PostgreSQL offline SQL compilation requires no connection.
A production downgrade would remove new assessment/ceiling fields and is not a safe data-preserving
rollback after new submissions: back up and prefer a forward repair. No staging database was contacted.

## Verification and remaining acceptance

Exact final commands/results are recorded in BUILD_STATUS.md. No full backend suite or Playwright ran.
Focused tests cover policy, grading/secrecy, attempts/replays, legacy/explicit awards, opinion neutrality,
physical empty evidence, membership, suspension, recognition metrics, notifications and migration history.
Frontend checks cover serializers, scope separation, focus behavior and retained layout contracts; these
are not a substitute for browser/device acceptance.

Executed from repository root (Python uses `.venv/Scripts/python.exe`):

```text
python -m pytest tests/test_task_staging_reconciliation.py tests/test_tasks.py tests/test_task_type_and_evidence.py tests/test_governance_migration.py tests/test_task_evidence_migration.py tests/test_task_assignment_details_api.py tests/test_organizer_task_queue_api.py tests/test_recognition_awards.py tests/test_auth_refresh_behavior.py tests/test_admin_configuration_product.py -q --tb=short
41 passed, 2 dependency deprecation warnings (181.57s)

python -m pytest tests/test_task_staging_reconciliation.py tests/test_task_evidence_migration.py tests/test_tasks.py tests/test_task_assignment_details_api.py tests/test_organizer_task_queue_api.py tests/test_admin_configuration_product.py -q --tb=short
24 passed, 2 dependency deprecation warnings (168.80s)

python -m ruff check <changed and new Python files>
All checks passed

git diff --check
Passed
```

Executed from `frontend` after the final frontend changes:

```text
node --test scripts/test-task-learning.mjs scripts/test-governance-layout.mjs scripts/test-management-layout.mjs
38 passed, 0 failed
npm run build
Passed: TypeScript + Vite, 94 modules
npm run lint
Passed: ESLint
```

Implemented but verification outstanding:

- Manual create/assign/submit/reject/retry/approve flows at 320/360/390/414/768/1024/1280 pixels;
  keyboard focus, nested discard confirmation, screen readers and mobile dialog scrolling.
- Refresh/navigation/logout/account/community switching with encrypted drafts, storage denial, network
  failure, lost-response replay and stale assignment/policy changes.
- Real quiz/checkpoint passing/failing/lockout; survey contrasting opinions; private-answer inspection;
  actual notification receipt and achievement presentation using staging rules.
- Super Admin ceiling configuration, lower-ceiling future awards, absent rules, zero-point tasks and
  unchanged historical totals. Reconfirm the working free/paid ticket, attendance/QR and R2 media paths.
- Disposable PostgreSQL clone upgrade, simultaneous submission/verification/ceiling changes, uniqueness
  race recovery, and measured large-community/mobile/slow-network performance.

Not yet implemented, previously identified specification-backed work in the inspected governance area:
the dedicated create-community frontend journey (authorized backend exists). This pass does not claim
to implement that separate screen or reassess unrelated project requirements. No new LMS, randomized
checkpoint selection or global rank semantics are claimed as specification obligations.

## Changed-file inventory

```text
BUILD_STATUS.md
docs/TRACEABILITY_MATRIX.md
docs/TASK_STAGING_RECONCILIATION_2026_09_13.md
frontend/src/AdminPointRules.tsx
frontend/src/AdminRecognition.tsx
frontend/src/HomeDashboard.tsx
frontend/src/OrganizerEvents.tsx
frontend/src/OrganizerTaskQueue.tsx
frontend/src/PlatformGovernance.tsx
frontend/src/Tasks.tsx
frontend/src/LearningTask.tsx
frontend/src/PlatformPointCeilings.tsx
frontend/src/RevealFocus.tsx
frontend/src/formRecovery.ts
frontend/scripts/test-task-learning.mjs
src/api/admin_configuration.py
src/api/auth.py
src/api/tasks.py
src/api/point_ceilings.py
src/main.py
src/models/__init__.py
src/models/configuration.py
src/models/task.py
src/schemas/task.py
src/services/impact.py
src/services/task.py
src/services/point_policy.py
src/services/task_assessment.py
migrations/versions/c8d9e0f12345_task_evidence_and_point_ceilings.py
tests/test_admin_configuration_product.py
tests/test_governance_migration.py
tests/test_tasks.py
tests/test_task_evidence_migration.py
tests/test_task_staging_reconciliation.py
```

## Superseding note — 2026-09-19: Organizer least-privilege boundary

Appended rather than substituted. Everything above stands as the record of what was verified on
2026-09-13; the statements below are corrected here, in a dated section, instead of being edited in
place. Nothing above was rewritten.

### Member visibility — supersedes the assignment-selection paragraph

The paragraph "Assignment selection searches display name/username … search is client-side, not a
claimed new server-paginated directory" described the *then-current* boundary. The boundary is now:

- `GET /communities/{community_id}/members` — the directory, contact details included — requires a
  community **Admin** membership. It is governance data and amounts to a bulk export of personal
  information that operational event and task delivery never needs.
- Organizers resolve **one member at a time** through
  `GET /communities/{community_id}/members/search`. It requires a real query of at least two
  characters, is capped at `MEMBER_SEARCH_LIMIT` (10) with no offset to page through, and can only
  see `ACTIVE` memberships belonging to active users. Left, suspended and non-member users are not
  reachable, and a user outside the community is indistinguishable from a user who does not exist.
- An email address is echoed only when the query *was* that exact address. A display-name or
  username match never returns an address, so a name search is not a harvesting route.
- LIKE wildcards in `q` are escaped, so a query of `%` cannot be turned into a directory dump.
- Each search is audited as a query kind, a truncated digest and a result count — never the raw
  term, so the audit trail cannot itself become a store of members' addresses.

The performance observation in that paragraph is unaffected and remains an external load-test
concern.

### Organizer task authority — clarifies the task sections

The task material above describes creation, assignment, submission and verification without saying
who may perform them. Current authority:

| Actor | Task authority |
|---|---|
| Participant | Submits and reads their own assignments. **Unchanged** by this reconciliation. |
| Organizer | Creates tasks; manages, assigns, verifies and rejects **the tasks they created**. |
| Community Admin | Manages **all** tasks in the community. |
| Super Admin | Unchanged platform oversight. |

The enforcement point is the shared helper in `src/authorization.py`, which resolves ownership from
the task's creator and admits a community Admin as an override.

### Other boundaries settled in the same pass

- **Attendance.** Verification, the review queue and the roster follow event-scoped authority —
  event owner, an assigned `EventStaff` member holding a suitable role, or a community Admin — not
  membership in the community. An Organizer of the community who does not run the event reads and
  resolves nothing on it.
- **Event analytics.** `event_summary` is event-scoped on the same terms, with delegated staff
  limited to the `manager` role. Community-wide analytics remain Admin-gated and were not narrowed.
- **Ticket validation.** `POST /events/{event_id}/tickets/validate` now authorizes through the
  shared event-scoped helper, so an appointed member-level `EventStaff` with a door role is admitted
  instead of being refused by the community-role floor. Ticket ownership, ticket status, event
  lifecycle and tenant checks were not weakened.
- **EventStaff delegation.** The write path to appoint and revoke event staff exists, so the
  delegation the model describes is usable rather than only readable.
- **Frontend.** Management navigation is derived from the selected community membership role rather
  than the platform role, and a stale or hand-set view is resolved back to a permitted destination.
  This is presentation only — backend authorization remains the enforcement point.

### Specification clauses not aligned with the above

`TICKVENDOR_SPEC.md` was **not** modified. §5 (USER ROLES) lists, under **Organizer**, "Assign
tasks" (line 185), "Verify task completion" (line 186) and "View analytics" (line 189) with no
ownership qualifier, and lists "Manage community-wide activities" (line 202) and "View community
analytics" (line 203) as things a **Community Administrator** can do *additionally*. The
implementation reads the unqualified Organizer entries as scoped to what the Organizer runs, which
is what makes the *additionally* clause meaningful; it does not narrow anything the spec grants
Admins. §5 (USER ROLES) also lists "Validate tickets" for Organizer without describing delegated
event staff, so the `EventStaff` roles carry no role semantics in the specification at all. These
are recorded as conflicts, not as new requirements.
