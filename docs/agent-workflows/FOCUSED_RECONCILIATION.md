# Focused reconciliation workflow

For a bounded feature, bug, or single-domain reconciliation. For schema changes also use `MIGRATION_SAFETY.md`; for authorization work also use `TENANT_SECURITY_REVIEW.md`.

## 1. Establish state

* Run `git status --short` and `git diff` for the area you will touch, and preserve existing tracked and untracked work.
* Identify the exact domain: files, routes, services, models, tests, and current migration head.

## 2. Scope the reading

* Read only the specification sections that govern the domain.
* Inspect the existing implementation and tests, plus the newest relevant `BUILD_STATUS.md` entry and matching `docs/` domain document.
* Do not read `docs/TRACEABILITY_MATRIX.md`, other dated reconciliation documents, or the rest of the repository unless the evidence leads there.

## 3. Reproduce or trace

* Reproduce the reported behaviour with a focused test, a real request, or a traced code path.
* State the root cause before changing code. Do not patch symptoms.

## 4. Fix minimally

* Make the smallest coherent change that fixes the root cause and follows existing architecture and conventions.
* Reuse existing services, schemas, and helpers instead of adding a parallel implementation.
* Keep authorization, tenant scope, transaction boundaries, and idempotency intact.

## 5. Focused security review

* Confirm the change cannot cross a tenant, role, or ownership boundary, leak private data, or enable replay or duplicate side effects.

## 6. Focused tests

* Run the tests covering the changed and risk-relevant behaviour, plus changed-file Ruff, lint, type, or build checks.
* Do not run the full pytest or Playwright suites unless the risk genuinely requires it.
* Never weaken, skip, or delete an assertion to obtain a pass.

## 7. Report

* State what changed, why, the exact checks executed with their results, and whether the outcome is implemented + verified or implemented but verification outstanding.
* Record durable evidence in `BUILD_STATUS.md`, and design detail in the matching `docs/` domain document.
* No commit, push, or deploy unless explicitly requested.
