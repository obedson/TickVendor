# Migration safety workflow

For Alembic and schema changes. The permanent rules in `docs/AGENTS.md` apply throughout.

## 1. Establish the graph

* Read the actual head with `alembic heads` and `alembic current`, and inspect the revisions in `migrations/versions/`.
* Set `down_revision` to the real current head. Never assume it.
* Keep a single head.

## 2. Keep models and migrations consistent

* The migration must reproduce the model change exactly: columns, types, nullability, defaults, server defaults, foreign keys, indexes, unique constraints, and check constraints.
* Update the SQLAlchemy model under `src/models/` in the same change so the schema and models cannot drift.

## 3. Protect populated data

* Assume real rows exist: users, profiles, memberships, events, tickets, payments, attendance, tasks, Impact transactions, recognition, and audits.
* Never silently rewrite, delete, or reclassify historical financial, Impact, or recognition data.
* Backfills must be explicit, idempotent, and safe to re-run.
* SQLite table rebuilds need connection-local foreign-key handling; verify and restore foreign-key integrity around the rebuild.

## 4. Execute on a disposable database

* Run `upgrade` against a fresh or disposable database, then `downgrade` where a downgrade is safe and required, then re-`upgrade`.
* Confirm there is no model/schema drift (`alembic check`) and, where existing tables are touched, that populated rows survive unchanged.
* Compile the DDL for PostgreSQL where available. SQLite success does not prove PostgreSQL behaviour.

## 5. Boundaries

* Never run migrations against live, staging, or remote databases without explicit authorization.
* Live PostgreSQL execution, locking on large tables, and concurrency behaviour stay externally unverified until actually executed there.

## 6. Report

* Record the revision id, its parent, what changed, the populated-data result, the exact commands executed with results, the downgrade and re-upgrade result, and the remaining external verification.
