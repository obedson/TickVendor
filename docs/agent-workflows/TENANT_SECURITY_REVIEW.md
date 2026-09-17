# Tenant and security review workflow

For authentication, authorization, membership, moderation, or abuse-resistance work. Pair with `FOCUSED_RECONCILIATION.md`.

## Boundaries to verify

* Authentication: token issuance, expiry, refresh, revocation, session invalidation, email verification, and suspension gates.
* Roles: participant, organizer, community admin, and super admin, assigned and changed only through authorized backend paths.
* Tenant scope: community and organization membership checked server-side on every read and write, never inferred from a path or payload identifier.
* Ownership: a user may act only on their own tickets, orders, submissions, evidence, points, and profile.

## Attacks to test

* IDOR on every identifier in the changed surface, including sequential ids.
* Cross-community and cross-organization access using a valid token from another tenant.
* Privilege escalation: self-promotion, role supplied in a request body, legacy or unused role routes, and admin endpoints reachable by non-admins.
* Suspended, invited, pending, or removed membership still able to read or act.
* Enumeration through distinguishable responses, timing, or error text for existing versus nonexistent accounts and resources.
* Private evidence and files: access controlled by the same authorization as the parent record, not by URL possession.
* Replay and duplicate side effects from repeated webhook, confirm, claim, or reward requests.
* Point or Impact manipulation, forged attendance, self-confirmation, and peer-confirmation farming.

## Rules

* Frontend hiding and route guards are never authorization. Every boundary is enforced in the backend.
* Every sensitive state transition is audited.
* Add negative authorization tests: the request must fail, not merely render differently.
* Fix issues within the application's control; record provider or infrastructure gaps as external verification outstanding.

## Report

* Record the boundary reviewed, the attack executed, the observed result, the fix, and the residual external verification.
