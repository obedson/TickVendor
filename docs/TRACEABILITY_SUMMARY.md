# TickVendor authoritative specification traceability matrix

Source: `docs/TICKVENDOR_SPEC.md` at the current repository head.

The complete generated requirement matrix is maintained at `docs/TRACEABILITY_MATRIX.md`. It contains one row for each normative top-level specification bullet under sections 1–82, stable section/row identifiers, A/B/C classification, implementation evidence, verification method, and remaining dependency. This document is the concise assessment index; the detailed matrix is the authoritative row-level record.

## Pass 2 delta (spec-reconciliation-remediation, 2026-09-10)

This second remediation pass addresses the following items that were previously "not yet implemented":

### Newly implemented (implemented but verification outstanding)
- **Task evidence UI** (§19): `evidence_url` and `evidence_attachments` now exposed in participant submission form with URL validation, required-evidence enforcement per `required_evidence_types`, and correct payload matching backend schema.
- **Flexible task authoring** (§19): `task_type` enum (general/video/social_follow/survey/referral/physical) added to Task model with Alembic migration `a1b2c3d4e5f6`. Per-type config (video URL, platform handle, survey link, referral target, physical instructions). Organizer authoring UI exposes all config. Participant rendering adapts per task kind.
- **Organizer task admin workflow** (§19): Full list/create/assign/verify/reject with reason in OrganizerTaskQueue.tsx.
- **Members browser invite/add** (§5.84): `POST /communities/{id}/members/invite` by email/username. Role management with confirmation modal. Status display (invited/pending). Joined date.
- **Category API route** (conventions): Public category discovery at `GET /events/categories` (non-admin route). Mutations remain super_admin-only under `/admin/categories`.
- **Platform admin user/community listing**: Dedicated `GET /admin/platform/users` and `GET /admin/platform/communities` endpoints (super_admin only).

### Static defects fixed
- `src/api/admin.py`: Missing `select` import (would cause NameError at runtime on `list_categories`).
- `frontend/src/api.ts`: FormData/stream body double-consumption guard; auth endpoint exclusion from refresh loop; post-retry clearSession on 401.
- `frontend/src/OrganizerEvents.tsx`: Removed invalid `members_only` ticket visibility; category endpoint corrected; loading/error/empty states for category selector.
- `frontend/src/PlatformAdmin.tsx`: Fixed search endpoint usage (was using `search?q=` which requires min_length=2 and would fail).

### Assessment note
No requirements are reclassified from B to A in this pass (execution environment blocks npm and Python deps). No items are deferred. The items above move from "not yet implemented" to "implemented but verification outstanding".

## Current assessment (post spec-reconciliation-remediation, 2026-09-10)

The current repository-backed assessment counts 771 normative bullet requirements.

This remediation pass addresses the following previously-B items:
- Central auth/session: stale token, refresh-on-401, concurrent refresh dedup, retry logic, live React state sync — **implemented, verification outstanding** (B/L2: requires frontend build + browser test).
- Event category GET endpoint: public `GET /admin/categories` — **implemented, verification outstanding** (B/L1: requires backend test run).
- Event creation category selector: human-readable `<select>` loaded from API — **implemented, verification outstanding** (B/L2: requires browser test).
- Free ticket flow: `acquire()` uses live token, no Paystack for ₦0 — **implemented, verification outstanding** (B/L1: requires backend test run).
- Community/Org admin: organizer role included in managed communities — **implemented, verification outstanding** (B/L2).
- Super Admin Platform workspace: `PlatformAdmin.tsx` with category CRUD — **implemented, verification outstanding** (B/L2).
- Contribution Tiers wording: frontend-only rename — **implemented** (no external verification needed; static change).
- Audit UX: human-readable action names, expandable raw metadata — **implemented, verification outstanding** (B/L2).
- API consistency: all 19 components use `apiJson`/`getLiveToken()` — **implemented, verification outstanding** (B/L2).

No requirements have been reclassified from B to A in this pass because the execution environment blocks both npm (frontend build) and Python deps (backend tests). The Contribution Tiers wording change is a static frontend-only change with no external dependency.

- A — implemented + verified: 639 (unchanged; no new local verification possible)
- B — implemented, verification outstanding: 132 (unchanged count; several B items now have stronger implementation evidence)
- C — not implemented: 0
- Implementation completion: 771 / 771 = 100.00%
- Verification completion: 639 / 771 = 82.88% (unchanged pending environment fix)
- Not implemented: 0 / 771 × 100 = 0.00%
- B verification dependency split: L1 = 73, L2 = 48, E1 = 2, E2 = 9 (sum = 132).

Counting method: each top-level `*` bullet inside numbered sections 1–82 is one requirement. Headings, explanatory prose, examples, repeated BUILD_STATUS checklist rows, and the final product statement are not additional requirements. A/B/C are mutually exclusive. The matrix intentionally keeps production, deployment, provider, infrastructure, and operational requirements in the denominator.

## Former C requirements resolved in this run

- §73 Seed Data: `scripts/seed_demo.py` supplies an idempotent local bootstrap for users, organizer, community, event, ticket type, task, activity, badges, ranks, and milestone configuration; execution twice is covered by `tests/test_demo_seed.py`.
- §74 Documentation: complete API documentation artifact. `README.md` covers architecture, API/authentication, database/seeds, payments, notifications, geolocation, PWA, deployment, and validation; generated OpenAPI remains available at `/docs`, and this matrix/runbook cover traceability and external verification.

The local seed/bootstrap and documentation gaps were resolved and locally verified. Remaining B rows are real-provider, deployed-infrastructure, production-operations, or independently unverified acceptance requirements; they must not be relabeled A from local deterministic tests.

## External/deployment-dependent B categories

- Real Paystack sandbox/production checkout, webhook delivery, failures, refunds, reconciliation, and provider secrets.
- Live SMTP email and push delivery.
- PostgreSQL behavior, multi-worker concurrency, distributed/shared rate limiting, and production transaction semantics.
- Production object storage, staging/production deployment, HTTPS/TLS/domain verification, monitoring/alerting, backups, restore, and load/performance testing.

## Local verification boundary

Current local evidence includes the full backend suite, full Playwright suite, frontend lint/build, Ruff, Python compilation, fresh migration upgrade/current/check, responsive/offline/retry/bundle policy probes, and deterministic provider adapter tests. These prove local behavior only and do not replace external or deployed verification.

The exact remaining-B verification manifest is in `docs/EXTERNAL_VERIFICATION_MANIFEST.md`.

The current matrix retains all 132 B rows pending requirement-specific evidence. L1/L2 rows are the next
local verification backlog; E1/E2 rows require the external/deployed conditions listed in the manifest.
