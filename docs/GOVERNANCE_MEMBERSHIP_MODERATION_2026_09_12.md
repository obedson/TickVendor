# Governance, membership, moderation and personal-space reconciliation

Date: 2026-09-12. Starting commit: `4a89a0225df39c6b99df28f5f0b305a93588e3dc`.
Scope: finish the interrupted working tree, verify locally, and commit locally. No push,
deployment, Render configuration, environment-variable or secret changes. This is not an
overall product assessment. Authoritative traceability counts/percentages are unchanged.

## Evidence and recovery

The current code, rather than prior agent claims, was inspected. The interrupted files
were preserved. Community and Platform Admin removals are intentional component extractions:
`Communities` mounts `CommunityLifecycle`; `PlatformAdmin` retains `CategoryManager` and
mounts `PlatformGovernance`. Existing responsive member tables, invitation functionality,
category controls and workspace routing remain. New routers are registered in `src/main.py`;
OpenAPI generation succeeds and the route/method inventory has no duplicates.

Concrete defects corrected in this pass:

- Invitations had no participant response journey; `/communities/me` hid non-active states.
- Community creation could grant Admin authority to an ordinary participant.
- Existing role/status routes could change Admin authority or bypass invitation acceptance.
- The legacy `/admin/communities/{id}/memberships/{id}/role` route independently changed roles;
  it now delegates to the same governance service, requires a reason and uses the same audit.
- Platform user/community directories were read-only; no reversible policy moderation or
  complete administrator-assignment journey was connected to those screens.
- Community member profile lookup used the user ID as the Profile primary key; lookup now
  uses `Profile.user_id`, retaining private-profile redaction.
- Two attendance mutation routes did not call the common event lookup and therefore initially
  bypassed the suspension gate. QR verification and organizer verification now check it too.
- The search response test needed the additive visibility/access fields. The location source
  test referenced main.tsx and an old timeout; HEAD already placed that UI in Attendance.tsx
  with an 8-second timeout. Only the stale test was updated; GPS behavior was not rewritten.

## Role model and administrator governance

Product authority: specification section 5 gives Community Administrators community/member
management and Super Administrators full platform access. The focused user request further
defines Admin assignment/demotion as exclusively Super Admin governance.

- Platform: ordinary Participant/User or Super Admin. Legacy enum values remain for compatibility;
  these workflows neither grant them nor treat Community Admin as a platform role.
- Community: Member < Organizer < Admin, always scoped to a community membership.
- Super Admin needs no ordinary membership to use platform governance APIs.
- Ordinary Admin can invite Member/Organizer, approve/reject requests, change established
  Member/Organizer roles and suspend/reactivate those memberships. Existing Admin rows and
  the actor's own row have no mutation controls. Non-Admin viewers get no management controls.
- Backend restrictions cover both member-management API variants. Altered IDs or hidden UI
  controls cannot grant authority. Wrong-community membership IDs and unauthorized actors fail.
- Platform Admin > Communities > Inspect > Assign Community Admin searches existing active
  users and creates/promotes/reactivates an Admin membership, with confirmation and reason.
- Established memberships can be changed to Member/Organizer/Admin through platform inspection.
  Admin demotion uses the same audited service. Suspended/invited/pending history is not deleted.
- Community creation is restricted to an existing active community Admin or Super Admin.
  Creation grants the creator Organizer, not Admin; Super Admin must appoint the local Admin.

### Last local Admin decision

No hard minimum-local-admin invariant is introduced. The specification does not state one;
the membership schema has no mandatory Admin relation, and Super Admin retains independent
platform authority. This is a repository-backed implementation decision, not a claim that
the spec explicitly discusses administrator-less communities. A new community can await
appointment, and Super Admin can deliberately demote/deactivate the final local Admin.
Inspection displays the active Admin count and warns that approvals/configuration then
depend on Super Admin until an Admin is appointed. The final-Admin demotion and recovery
are tested. Ordinary Admins cannot change Admin authority or leave before Super Admin
demotes them. No automated or participant path silently strips local Admin authority.

## Membership access, visibility and transitions

`is_public` controls discovery, independently of `membership_access`:

| Policy | Participant action | Result |
| --- | --- | --- |
| open | Join | Active Member |
| approval_required | Request to Join | Pending Member; Admin approval required |
| invite_only | Respond to existing invitation | Accept activates the invited role |

Existing communities default to INVITE_ONLY in the migration, preserving invitation-based
access rather than silently opening enrollment. Public discovery excludes private, inactive
and soft-deleted communities. Private communities without a prior membership cannot be joined
by guessing an ID. Existing invitees see their community through their own membership list.

| Action | Source | Destination / rule |
| --- | --- | --- |
| Invite | No membership, LEFT, DECLINED | INVITED; Member/Organizer for ordinary Admin |
| Accept | INVITED | ACTIVE, preserving the invited role |
| Decline | INVITED | DECLINED |
| Open join | None, LEFT, DECLINED | ACTIVE Member; never restores an old privileged role |
| Request | None, LEFT, DECLINED | PENDING Member |
| Withdraw | PENDING | LEFT |
| Approve | PENDING | ACTIVE Member, never Admin |
| Reject | PENDING | DECLINED |
| Leave | ACTIVE non-Admin | LEFT, without deleting membership or evidence |
| Deactivate | ACTIVE Member/Organizer | SUSPENDED; Admin targets reserved to Super Admin |
| Reactivate | SUSPENDED | ACTIVE; cannot be used to activate INVITED/PENDING |

Repeated successful actions that already have the requested resulting state are no-ops.
Repeated identical invitations, joins, requests, acceptance and approval do not add rows or
repeat audit/notifications. Invalid transitions return 409. SUSPENDED users cannot self-rejoin
or use invitation acceptance to bypass administrator action. Rejoining LEFT/DECLINED respects
the current policy; invite-only communities require a new invitation. Leaving, withdrawing
and declining can preserve/close personal membership state during community suspension.
The participant UI shows My Communities, Discover, Pending Requests, Invitations and Past
Memberships, and refreshes workspace membership options after a transition.

Sensitive transitions lock the community row on PostgreSQL and preserve the existing unique
community/user membership constraint. Real concurrent PostgreSQL verification remains outstanding;
SQLite functional tests establish sequential idempotency, not PostgreSQL lock behavior.

## Reversible moderation and history

Platform directories support names/titles, user email/username, moderation state, creation-date
filters, content lifecycle status, community and creator filters. Lists use 50-record pages;
membership inspection is paginated with Admins first. Community/creator selectors support search.
User inspection includes email verification, platform role, status and community memberships.
Community inspection includes policy, visibility, active member/Admin counts and memberships.
Content inspection includes title, creator, community, description and normal lifecycle status.

- User suspension sets `User.is_active=false` and revokes existing refresh sessions. Existing
  access tokens fail the database-backed current-user check while inactive. Reactivation restores
  access eligibility, but does not un-revoke refresh sessions. No payment or evidence row is deleted.
  Super Admin/self suspension is denied to avoid platform lockout through this ordinary tool.
- Community suspension uses existing `Community.is_active`. Ordinary community authority fails
  while inactive; Super Admin inspection/governance remains possible without membership.
- Event, opportunity and task policy suspension uses separate `is_suspended` booleans. It never
  repurposes cancelled/completed/refunded/expired or changes the normal lifecycle on restoration.
- Required nonblank reason, confirmation and append-only audit accompany changed moderation state.
  Repeating the same desired state is idempotent and produces no duplicate audit/notification.
- No separate competing moderation ledger was introduced. Existing AuditLog records actor, target
  type/ID, community, timestamp, reason, previous and resulting state. Platform history renders
  human-readable actors, target names, reasons and resulting state rather than raw JSON.
  Inspection links filter history to the target/community or user's membership targets.

### Direct-access boundary

The shared availability service excludes suspended content/inactive communities from event
discovery, event search, public organizer event lists, opportunity discovery and task lists.
It guards event management, ticket catalog/order acquisition/QR validation, attendance check-in,
QR/peer/organizer verification and review mutation, opportunity publish/edit/join/complete/verify,
and task assign/accept/start/submit/verify. Community management still checks scoped authority.
Knowing a direct event/opportunity/action URL does not bypass the gates.

Historical data is retained: personal ticket wallet, owned assignment details, personal registration
history, profile progress and immutable rows remain. Read-only attendance roster/review can inspect
an individually moderated event under existing community authorization. A suspended community
still blocks ordinary management authority; Super Admin can inspect it. Suspension does not erase
financial history, revoke earned recognition or cancel an already-started payment reconciliation.
Payment provider verification/callback logic remains unchanged so pending financial reconciliation
can finish without creating an unaccounted external-money outcome. New acquisition and entry are gated.

## Audits and notifications

Membership audit actions: `membership.joined`, `requested`, `invited`, `accept`, `decline`,
`withdraw`, `leave`, `approved`, `rejected`, `role_changed`, `deactivated`, `activated`,
`admin_assigned` (each with the `membership.` prefix). Moderation uses `moderation.suspended`
and `moderation.restored`; the target type distinguishes user/community/content. Community
policy updates retain `community.updated`; creation retains `community.created`.

Governance reuses `notify` and existing notification preferences/community rules. Invitation,
approval/rejection, role/status changes and Admin assignment notify the affected user when the
actor differs. Pending requests notify active community Admins. Moderation notifies the affected
user/content creator and active community Admins, deduplicating recipients. Actor-initiated joins,
acceptance and leaving do not send redundant self-notifications; they update the UI and audit.
No-op repeats skip notifications. In-app rows participate in the governance transaction;
email/push use the existing provider helper. Provider delivery/receipt and crash-boundary behavior
are not verified here; no new claim of exactly-once external delivery is made.

## Participant record policy and archives

`PersonalArchive` is a per-user presentation preference, not a replacement resource state.
It has an owner FK, typed item discriminator, item ID, archived timestamp, a unique
owner/type/item constraint, type check constraint and owner/type index. API ownership checks
use the actual Ticket attendee, TaskAssignment assignee, OpportunityRegistration participant
or Notification recipient. Another user's archive/unarchive request receives 404. Only the
preference is deleted on restore. PostgreSQL owner-row locking and uniqueness serialize
preferences; repeated archive/restore calls are no-ops. No domain cascade is invoked.

| Record | Personal presentation policy |
| --- | --- |
| Notifications | Existing mark-read remains; archive/archived/restore without deleting messages |
| Tickets | Active/Upcoming, History, Archived; used/cancelled/refunded/expired or ended-event tickets can be archived |
| Tasks | Existing current/completed views plus owned history/archive; verified assignments are eligible |
| Opportunities | Available catalog plus My Registrations, History, Archived; completed/verified/rejected or closed/cancelled/ended participation eligible |

Reserved/pending-payment tickets and tickets attached to unconfirmed/failed orders remain excluded,
matching the wallet's issuance filter. QR credentials and full ticket display remain intact.
Generic personal-item APIs never expose QR tokens. The existing evidence APIs continue returning
their authoritative records; personal views apply the owner-specific archive preference. History
pages filter the 50-record page and expose next/previous record navigation. Failed preference loads
show errors and preserve available data instead of silently hiding it. No archive flag is written
onto shared events, tasks, opportunities, tickets or attendance.

Participants may clear their own removable profile fields through the existing profile update API;
there is no new hard-delete or draft subsystem. They may archive the four eligible types above.
They may not hard-delete successful payments/orders, used/refunded tickets, attendance/verification,
Impact ledger entries, badge/milestone/rank awards, verified task/contribution evidence, audit or
moderation history through these workflows. Corrections use the existing authorized domain
reversal/revocation/status/correction mechanisms, not personal archive or destructive deletion.

## API inventory (all paths below /api/v1)

- `GET /communities/me`: includes all membership states and community access/active status.
- `GET /communities/discover?q=&offset=`: public active communities and caller's membership state.
- `POST /communities/{community}/membership/{join|accept|decline|withdraw|leave}`.
- `POST /communities/{community}/membership-requests/{membership}/{approved|rejected}` with reason.
- Existing community create/update/member list/invite/role/status routes remain; access fields are
  additive, `is_active` is not writable through ordinary community updates, sensitive mutations require reason.
- Legacy `PATCH /admin/communities/{community}/memberships/{membership}/role` now uses governance.
- `GET /admin/platform/governance/{user|community|event|opportunity|task}`: scoped Super Admin directory.
- `GET /admin/platform/governance/{kind}/{target}?membership_offset=`: inspection.
- `POST /admin/platform/governance/{kind}/{target}/moderation`: suspended boolean and reason.
- `POST /admin/platform/governance/community/{community}/administrators`: existing user ID and reason.
- `PATCH /admin/platform/governance/community/{community}/memberships/{membership}`: role/status action and reason.
- `GET /admin/platform/governance/history?target_id=&offset=`: human-readable audit history.
- `GET /me/archive`, `GET /me/personal-items/{notification|ticket|task|opportunity}?offset=`.
- `POST /me/archive/{kind}/{item}` and `DELETE /me/archive/{kind}/{item}`: archive and remove preference.
- Wallet responses add `event_ends_at` for historical classification; offline type accepts older cached tickets.

## Migration

Revision `b7c8d9e0f123`, down revision `9f0a1b2c3d4e`; branch_labels and depends_on are None.
The prior actual schema head was checked, not guessed from an older migration name. There is one
revision lineage/head and no duplicate revision. Adds community membership_access, content suspension
columns/indexes, membership community/status index and personal archive table/constraints/index.
PENDING and DECLINED fit the existing non-native varchar membership enum; no PostgreSQL native-enum
rewrite is required. Existing communities receive INVITE_ONLY; existing content is not suspended.

Verified in an isolated temporary SQLite database: all earlier migrations to the previous head,
upgrade to the new head, columns/indexes/constraints, downgrade to previous head and re-upgrade.
PostgreSQL upgrade SQL compiles with GUID/boolean/default/constraint definitions. This is not an
executed live PostgreSQL migration. No production database was modified. Upgrade is additive.
Downgrade intentionally drops the newly introduced preferences/moderation columns: use backups
and an explicit operational rollback decision, not an unattended live downgrade.

## Focused verification

Combined command (no full backend suite):

```text
venv/Scripts/python.exe -m pytest tests/test_governance_membership.py tests/test_platform_moderation.py tests/test_personal_archive.py tests/test_governance_migration.py tests/test_community_management.py tests/test_authorization.py tests/test_search_authorization.py tests/test_admin_audit_actions.py tests/test_ticketing.py tests/test_free_ticket_flow.py tests/test_activity_opportunities_api.py tests/test_tasks.py tests/test_organizer_attendance_operations_api.py tests/test_event_image_upload.py -q
```

Result: **38 passed**; one existing Starlette/httpx deprecation warning. Includes role escalation,
legacy-route bypass, cross-tenant denial, final-Admin recovery, complete membership transitions,
moderation reason/idempotency/history/direct-action gates, archive ownership, migration upgrade/
rollback/re-upgrade and related ticket/free-ticket/task/opportunity/attendance/private-media regressions.
The archive regression additionally snapshots populated tickets, attendance, Impact transactions,
badge/milestone awards, task assignments, opportunity registrations and notifications across archive/restore.

Frontend command: `node --test frontend/scripts/test-governance-layout.mjs frontend/scripts/test-management-layout.mjs frontend/scripts/test-offline-tickets.mjs frontend/scripts/test-location.mjs`.
Result: **34 passed**. These are focused source-contract/helper tests, not rendered browser acceptance.
`npm run build` (including `tsc -b`) and `npm run lint` pass. Ruff is restricted to changed Python files.
Final Ruff and `git diff --check` pass. The strengthened archive test and final governance/moderation
rerun pass **9 tests**. Working-tree/commit verification is recorded in the final report.
No Playwright, full backend suite, staging login or deployment was run.

## Human tester acceptance checklist — NOT performed in this run

Use distinct Participant P, Community Admin A in Community A, Admin B in private Community B,
Organizer O and Super Admin S. Seed controlled test records through normal authorized workflows.

### Participant

- [ ] Discover public communities; private B is absent and guessed join returns no community.
- [ ] Join OPEN community; repeat; exactly one ACTIVE Member, no privileged role.
- [ ] Request APPROVAL_REQUIRED; see Pending; withdraw; request again; observe approval/rejection.
- [ ] Receive an invitation; accept; receive another; decline; verify duplicate and stale responses.
- [ ] Leave, rejoin according to access mode, and verify retained tickets/attendance/Impact/achievements.
- [ ] Mark notification read, archive, find archived, restore, reload/sign in again and confirm persistence.
- [ ] Archive/restore eligible ticket history; active tickets cannot be archived; failed reservations stay hidden.
- [ ] Archive/restore verified task and completed/closed opportunity participation; evidence remains accessible.
- [ ] Confirm immutable records have no destructive participant delete controls.

### Community Admin / Organizer

- [ ] Independently change discovery visibility and each access mode; existing members remain.
- [ ] Invite by email and username (including @username), Member and Organizer; inspect private-profile redaction.
- [ ] Review pending requests, approve/reject with reason; verify notifications and audit.
- [ ] Change Member ↔ Organizer; deactivate/reactivate; repeat and verify no duplicate action history.
- [ ] Confirm Admin rows/self have no forbidden controls; no Admin role in invitation/role selectors.
- [ ] Manually call both role APIs to try Admin escalation; expect denial. Attempt Community B IDs; expect denial.
- [ ] Organizer has no Admin-only policy/invite/member-management controls.
- [ ] Switch workspaces/communities while forms are open; no stale forms or selected-event leakage.

### Super Admin

- [ ] Search/inspect users, verification/status/memberships; suspend/reactivate; active-session calls fail while suspended.
- [ ] Confirm refresh sessions remain revoked and self/Super Admin suspension is blocked.
- [ ] Search/inspect communities; see Admins; assign existing user/promote Organizer; demote Admin with reason.
- [ ] Remove final Admin after reading warning; ordinary administration unavailable; S can appoint replacement.
- [ ] Suspend/reactivate community; ordinary direct management and new ticket/task/opportunity/attendance actions fail.
- [ ] Suspend event with reason; discovery/new acquisition/check-in/QR/organizer verification fail; wallet/evidence remain.
- [ ] Restore event; original lifecycle preserved; camera/manual scanner and free/paid-ticket journeys still work.
- [ ] Suspend/restore opportunity and task; direct join/completion/verification/assignment actions cannot bypass policy.
- [ ] Inspect target-filtered history: actor/name/reason/time/previous-result API states and readable UI result.
- [ ] Exercise directory and membership pagination beyond one page and search for older communities/users.
- [ ] Compare payment/order/ticket/attendance/Impact/recognition/audit rows before and after moderation/archive.

### Browser, accessibility and operational verification

- [ ] Repeat critical screens at **320, 360, 390, 414, 768, 1024 and 1280 pixels**: wrapping, no clipping,
  readable tables/cards, touch targets, labels, tabs, and dialog fit/scrolling.
- [ ] Keyboard-only dialogs: focus entry, tab containment, required reason, Escape/cancel, focus return and errors.
- [ ] Verify actual in-app/email/push receipt and preference suppression; record provider failures without secrets.
- [ ] Execute migration on a disposable PostgreSQL clone of the deployed head; verify defaults and preserved data.
- [ ] Concurrent join/invite/approval/moderation/archive requests on PostgreSQL; check one membership/preference,
  correct final state, audits and notifications. Provider-delivery crash boundaries need separate external evidence.

## Status boundaries / unfinished specification-backed work

The workflows above are implemented with focused local verification; browser/device accessibility,
human staging acceptance, live PostgreSQL migration/concurrency and external delivery are verification
outstanding, not claimed complete. The specification's community-creation capability has an authorized
backend API, but no dedicated create-community form was found in these screens; that UI journey remains
unfinished and is explicitly reported rather than hidden behind a completion assessment. No broader
project audit or reclassification of unrelated requirements was performed.
