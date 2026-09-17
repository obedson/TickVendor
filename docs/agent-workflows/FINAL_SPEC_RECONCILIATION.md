# Final specification reconciliation workflow

Heavyweight product audit. This is the only workflow allowed to determine overall product completion or recompute global requirement counts. It is expensive; do not use it for bounded tasks.

## Required inputs

* `docs/TICKVENDOR_SPEC.md`, reviewed completely, every numbered section.
* `docs/TRACEABILITY_MATRIX.md`, every normative requirement row.
* `docs/TRACEABILITY_SUMMARY.md` and `BUILD_STATUS.md`.
* The dated reconciliation documents under `docs/` for the domains being reassessed.
* Executed test evidence, external verification evidence, and deployed or provider evidence wherever the requirement depends on it.

## Rules

* Classify each requirement as exactly one of: **A** implemented + verified, **B** implemented but verification outstanding, **C** not yet implemented. There is no deferred category.
* Never infer verification from implementation. Local tests, mocks, and code inspection cannot establish staging, provider, PostgreSQL, or production behaviour.
* Do not fabricate, carry forward, or silently alter historical counts or percentages. Recompute only from an actual row-by-row reconciliation, and state the method.
* Keep the counting method explicit: each normative top-level specification bullet is one requirement; headings, explanatory prose, examples, and repeated checklist rows are not requirements.
* Requirements that depend on external providers, deployment, or hardware stay in the denominator.
* Do not change specification requirements during an audit. Record genuine specification ambiguities separately.

## Procedure

1. Establish `git status` and the available external and deployed evidence.
2. Walk the specification section by section against the matrix.
3. Verify or correct each row's classification from concrete evidence, and record the evidence plus the remaining dependency for every B row.
4. Reconcile the summary and `BUILD_STATUS.md` with the corrected matrix.
5. Execute the broader suites and record what actually ran.
6. Report classification counts, the counting method, new evidence, the B rows by dependency, and any unresolved observations.
