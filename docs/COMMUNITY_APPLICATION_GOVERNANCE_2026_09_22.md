# Community application and administrator governance

Date: 2026-09-22. This is a bounded governance extension and reconciliation, not an overall
project-completion assessment.

## Specification and extension boundary

`docs/TICKVENDOR_SPEC.md` §5 requires Community Administrators to create/manage communities and
gives Super Administrators full platform access. It does not prescribe an application approval
state machine. The reviewed application lifecycle, organization-scoped expansion, verified-admin
rule and final-admin protection are user-requested governance extensions compatible with §5; they
do not rewrite the original specification or its historical traceability.

## Authoritative role model

- Platform roles are now `participant` and `super_admin`. Legacy platform-wide `organizer` and
  `community_admin` values carried no authoritative community permission and are normalized to
  `PARTICIPANT` by migration. Membership rows are untouched.
- Community authority remains `Member < Organizer < Admin` on an active, tenant-scoped membership.
- Only a Super Admin can appoint, promote, demote, deactivate or reactivate a Community Admin.
- New and reactivated Admins must be active users with verified email. Super Admin authority is
  deliberately not duplicated into a community membership.
- The final active Community Admin cannot be demoted, deactivated, or suspended through ordinary
  platform moderation. A verified replacement must be appointed first.

## Community lifecycle

Independent communities use:

```text
DRAFT -> PENDING_REVIEW -> ACTIVE
                         -> REJECTED
ACTIVE <-> SUSPENDED
```

- Any active, verified user may save an independent application as a server draft or submit it.
- Draft and pending communities are inactive and undiscoverable. Submission is applicant-only,
  idempotent, audited and notifies active Super Admins once.
- Super Admin approval requires a selected active, verified initial Admin and atomically activates
  the community/organization, verifies the organization, activates the Admin membership, records
  reviewer/time/reason, audits both community and membership transitions, and notifies the applicant.
- Rejection keeps the application, membership history, reason and audit evidence while leaving the
  community and organization inactive.
- Moderation cannot masquerade as application review. Pending/rejected/draft records use the review
  workflow; active communities use reversible suspension/restoration. Restoration requires an
  active verified Admin.

## Organization-scoped creation

An active Community Admin may directly add a community only to an organization containing another
active community where that user is an active Admin. The creator becomes the new community's active
Admin atomically. A Community Admin in another organization receives 403. A Super Admin using this
direct API path must explicitly select a verified initial Admin. Creating an unrelated organization
always uses the reviewed application lifecycle.

## Data compatibility

Migration `d5e6f7a8b9c0` follows `c4d5e6f7a8b9`. Existing active communities become `ACTIVE` and
existing inactive communities become `SUSPENDED`; `is_active`, memberships, organization ownership,
community data and historical records retain their deployed meaning. Existing organization owner is
stored as submission provenance. Legacy user platform roles are normalized, but authoritative
community memberships are not rewritten. SQLite batch migration disables foreign keys only for the
table rebuild, verifies integrity, and restores enforcement; PostgreSQL remains transactional.

## API and UI

- `POST /api/v1/communities`: server draft, independent submission, or authorized same-organization
  creation according to `organization_id` and `submit_for_review`.
- `POST /api/v1/communities/{id}/application/submit`: applicant-only idempotent draft submission.
- `POST /api/v1/admin/platform/governance/community/{id}/review`: reasoned approve/reject action;
  approval accepts `initial_admin_user_id`.
- Platform Governance lists and filters lifecycle state, reviews pending applications, searches for
  verified initial Admins, and keeps review actions in governance history.
- Communities UI exposes local form recovery plus server draft/save/submit, pending/rejected history,
  and organization choices derived only from the caller's active Admin memberships.

## Manual/staging verification still required

- Verify draft persistence, submit, approve and reject with separate Participant and Super Admin
  accounts on staging PostgreSQL.
- Verify notification delivery/receipt and exact mobile/keyboard/dialog behavior.
- Verify same-organization creation and cross-organization denial using two real organizations.
- Verify replacement-Admin-before-removal and sole-Admin user-suspension rejection.
- Verify the populated migration against a staging backup before deployment. No deployment or live
  database mutation was performed in this implementation pass.
