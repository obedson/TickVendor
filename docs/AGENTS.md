# TickVendor - Permanent Agent Operating Rules

These rules apply to every coding-agent session in this repository: Codex, Claude, DeepSeek, Hermes, and comparable tools. They are deliberately short. Task-specific detail belongs in the authoritative documents below, not here.

Load only what the current task needs. The workflow index is `docs/agent-workflows/README.md`.

| Document | Purpose |
| --- | --- |
| `docs/TICKVENDOR_SPEC.md` | Authoritative product requirements and completion contract |
| `docs/agent-workflows/README.md` | Index of reusable task workflows |
| `BUILD_STATUS.md` | Persistent implementation, verification, and handoff record |
| `docs/TRACEABILITY_MATRIX.md` | Detailed requirement/evidence ledger (full reconciliation only) |
| `docs/TRACEABILITY_SUMMARY.md` | Concise traceability overview |
| `docs/*_YYYY_MM_DD.md` | Deep evidence for one domain or pass; read only the relevant one |
| `docs/EXTERNAL_VERIFICATION_RUNBOOK.md` | External/staging/provider verification procedure |
| `README.md` | Architecture, local setup, API, and deployment overview |

Do not merge these documents into one. Do not copy the specification feature inventory into agent instructions.

## 1. Specification authority

* `docs/TICKVENDOR_SPEC.md` is the authoritative completion contract. Read the sections relevant to the task; read the entire file only for a full reconciliation.
* The specification describes the complete initial product. There is no MVP/V1/V2 split. No specification requirement may be described as optional, future, deferred, nice-to-have, or post-V1.
* External, provider, or manual work is unfinished verification or unfinished implementation, never deferred work.
* The only valid requirement states are: **A** implemented + verified, **B** implemented but verification outstanding, **C** not yet implemented. Do not invent a "deferred" state.
* Do not invent requirements. Distinguish original specification requirements from user-requested extensions, and label extensions as extensions.
* Do not recompute or restate global completion counts or percentages inside a bounded task.

## 2. Working-tree safety

* Run `git status --short` and inspect `git diff` before substantial modification. The tree may contain intentional tracked and untracked work from interrupted sessions.
* Never reset, clean, restore, revert, stash, discard, rewrite, or switch branches unless the user explicitly authorizes it for the current session.
* Do not commit, push, or deploy unless explicitly asked.
* Prefer `inspect -> reuse -> refactor where necessary -> extend` over replacement. Do not rewrite working functionality or unrelated files to tidy them.

## 3. Scope-aware reading

Bounded task:

* read the relevant specification sections, not the whole specification;
* inspect the implementation, models, schemas, tests, and migrations the change touches;
* read the newest relevant `BUILD_STATUS.md` entry and the matching domain document under `docs/`;
* do not automatically ingest `docs/TRACEABILITY_MATRIX.md`, every dated reconciliation document, or the whole repository.

Full or final reconciliation only: read the complete specification and the required traceability evidence, as defined by `docs/agent-workflows/FINAL_SPEC_RECONCILIATION.md`.

## 4. Implementation discipline

* Loop: inspect, understand, reuse, minimally modify, integrate, focused test, verify, record.
* The backend/server is the source of truth for authorization, tenant scope, payments, tickets, attendance, task verification, contributions, rewards, and sensitive state transitions. Frontend state never substitutes for persisted server state.
* No fake functionality. Do not ship placeholder screens, invented statistics, simulated payment success, hard-coded progress or leaderboards, or "coming soon" where the specification requires a working feature. Seed/demo data is development-only.
* No hard-coded configurable business rules. Point values, badge/milestone/rank thresholds, and contribution, attendance, and verification requirements come from configuration or database structures wherever the specification makes them configurable.
* Preserve the real data flow end to end: database, backend, business logic, API, user action, backend validation, persistence, reward/notification, refreshed UI.
* Preserve transaction and data integrity. Ticket purchase, attendance/task/contribution rewards, badge awards, rank progression, and manual point adjustments must not leave partial states or duplicate awards.
* The payment, ticket, attendance, and achievement/recognition engines stay real, idempotent services rather than per-endpoint shortcuts.

## 5. Verification honesty

Never claim:

* a test passed when it was not executed;
* staging or provider behaviour was verified when only code was inspected;
* provider behaviour was verified using a local mock or adapter;
* a requirement is complete because code exists.

Label evidence explicitly as inspection-verified, locally executable-verified, or externally/staging/provider-verified. Report implementation status and verification status separately, using the A/B/C states in section 1.

Never weaken, skip, or delete an assertion to make a suite pass. Fix the cause or report the blocker.

## 6. Test economy

Bounded task: run the focused tests covering the changed or risk-relevant area, plus changed-file Ruff, lint, type, or build checks where the repository provides them. Do not run the full pytest or Playwright suites for reassurance alone.

Final verification: broader suites and complete acceptance are required.

Documentation-only or configuration-only passes must not run the full application test suite.

## 7. Tool and output economy

* Successful routine checks: report the check name, `PASS`, and a useful count. Do not reproduce hundreds of green log lines.
* Failures: report the failing command, the error, the relevant diagnostic evidence, the established root cause, and the fix or retry result. Never compress away debugging evidence.
* Search for the targeted section, symbol, or route before opening a large file. Do not re-read a large document already in context. Avoid repository-wide scans when the relevant files are known.
* Summarize a successful command chain as one line per check.
* Do not assert anything about your own token, context, or cache accounting unless the active client explicitly exposes it.

## 8. Progress and handoff

* Leave durable repository evidence for substantial work: what changed and why, the exact commands actually executed with results, failures and blockers, verification still outstanding, and the next required action.
* Update `BUILD_STATUS.md` for implementation, verification, and handoff state, and the matching `docs/` domain document for design detail.
* Append or update evidence. Never rewrite historical evidence or record verification that did not happen.

## 9. Security

Never expose, commit, log, or paste secrets. Do not ask the user to paste a secret into an agent conversation when the task can be completed without it.

Treat database credentials, `SECRET_KEY`, payment secrets, SMTP credentials, object-storage secrets, credentialed Redis URLs, deploy hooks, and provider tokens as sensitive.

Preserve tenant isolation, least privilege, IDOR protection, anti-enumeration, auditability, idempotency, replay resistance, and privacy. Frontend hiding is never authorization: enforce every boundary server-side.

## 10. External action safety

Without explicit authorization for the current session, do not push, deploy, modify provider or infrastructure settings, mutate live or staging databases, change environment variables, or alter Git remotes.

Implementing a feature does not authorize deploying it.

## 11. Interruption recovery

* Before a long run may be interrupted, leave concise durable evidence that a later session can resume from.
* On resume, read `git status`, the newest relevant `BUILD_STATUS.md` entry, and the matching domain document. Continue from repository evidence rather than reconstructing history from chat, and do not redo work already recorded as verified.

## 12. Final completion

* Only a full specification reconciliation may determine overall product completion. Use `docs/agent-workflows/FINAL_SPEC_RECONCILIATION.md`.
* Never declare TickVendor complete, or publish a new overall completion percentage, from a bounded task.
* A product-level completion claim requires complete specification review, the traceability matrix and summary, `BUILD_STATUS.md`, relevant reconciliation evidence, executed tests, and external or provider evidence where the requirement depends on it.

## 13. Product quality expectations

* Accessibility: keyboard navigation, semantic markup, labelled fields, visible focus and error states, sufficient contrast, and adequate touch targets.
* Mobile-first: small Android screens, touch interaction, slow connections, GPS permission flows, and QR scanning are first-class; desktop must remain excellent.
* Performance: no N+1 queries, unbounded queries, oversized responses or bundles, duplicate API calls, or obviously missing indexes.
* UX economy: complexity belongs in the backend. Keep navigation, forms, and dashboards compact; do not add unnecessary screens.
