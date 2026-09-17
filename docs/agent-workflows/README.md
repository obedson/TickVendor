# Reusable agent workflows

Load only the workflow relevant to the current task. The permanent rules in `docs/AGENTS.md` apply to all of them.

| Workflow | Use for |
| --- | --- |
| `FOCUSED_RECONCILIATION.md` | Normal bounded coding, bug fix, or single-domain reconciliation |
| `MIGRATION_SAFETY.md` | Alembic or schema changes |
| `TENANT_SECURITY_REVIEW.md` | Authentication, authorization, tenant isolation, or abuse-resistance work |
| `STAGING_ACCEPTANCE.md` | Manual or deployed staging and provider acceptance |
| `FINAL_SPEC_RECONCILIATION.md` | Heavyweight full-specification audit and completion assessment |

Everything else under `docs/` is specification or evidence, not a workflow. Do not load a workflow speculatively.

Workflows combine: for a schema change that touches authorization, load `MIGRATION_SAFETY.md` and `TENANT_SECURITY_REVIEW.md`.
