"""Normalize ticket/entitlement enum storage to SQLAlchemy member names.

Revision ID: c4d5e6f7a8b9
Revises: c1d2e3f4a5b6
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


ENUM_COLUMNS = (
    ("tickets", "assignment_state", 20, {"unassigned": "UNASSIGNED", "invitation_sent": "INVITATION_SENT", "claimed": "CLAIMED"}, "CLAIMED"),
    ("ticket_transfers", "status", 12, {"pending": "PENDING", "claimed": "CLAIMED", "cancelled": "CANCELLED", "expired": "EXPIRED"}, "PENDING"),
    ("entitlements", "redemption_mode", 12, {"qr": "QR", "code": "CODE", "either": "EITHER"}, "EITHER"),
    ("ticket_entitlements", "status", 12, {"available": "AVAILABLE", "redeemed": "REDEEMED", "expired": "EXPIRED", "revoked": "REVOKED"}, "AVAILABLE"),
    ("entitlement_redemptions", "status", 12, {"issued": "ISSUED", "redeemed": "REDEEMED", "expired": "EXPIRED", "cancelled": "CANCELLED"}, "ISSUED"),
)


def _normalize(table: str, column: str, values: dict[str, str]) -> None:
    for legacy, canonical in values.items():
        statement = sa.text(
            f'UPDATE "{table}" SET "{column}" = :canonical '
            f'WHERE "{column}" = :legacy'
        )
        if op.get_context().as_sql:
            op.execute(statement.bindparams(canonical=canonical, legacy=legacy))
        else:
            op.get_bind().execute(statement, {"canonical": canonical, "legacy": legacy})
    if not op.get_context().as_sql:
        remaining = op.get_bind().execute(
            sa.text(
                f'SELECT COUNT(*) FROM "{table}" '
                f'WHERE "{column}" IN ({", ".join(repr(value) for value in values)})'
            )
        ).scalar_one()
        if remaining:
            raise RuntimeError(f"Failed to normalize {table}.{column}")


def upgrade():
    context = op.get_context()
    sqlite = context.dialect.name == "sqlite" and not context.as_sql
    if sqlite:
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    try:
        for table, column, length, values, default in ENUM_COLUMNS:
            with op.batch_alter_table(table) as batch:
                batch.alter_column(
                    column,
                    existing_type=sa.String(length),
                    existing_nullable=False,
                    server_default=default,
                )
            # Run after SQLite's batch table rebuild as well as on PostgreSQL.
            if sqlite:
                with context.autocommit_block():
                    _normalize(table, column, values)
            else:
                _normalize(table, column, values)
        if sqlite and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first():
            raise RuntimeError("Foreign-key integrity failed after enum normalization")
    finally:
        if sqlite:
            with context.autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    context = op.get_context()
    sqlite = context.dialect.name == "sqlite" and not context.as_sql
    if sqlite:
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    try:
        for table, column, length, values, default in reversed(ENUM_COLUMNS):
            reverse = {canonical: legacy for legacy, canonical in values.items()}
            with op.batch_alter_table(table) as batch:
                batch.alter_column(
                    column,
                    existing_type=sa.String(length),
                    existing_nullable=False,
                    server_default=default.lower(),
                )
            if sqlite:
                with context.autocommit_block():
                    _normalize(table, column, reverse)
            else:
                _normalize(table, column, reverse)
        if sqlite and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first():
            raise RuntimeError("Foreign-key integrity failed after enum downgrade")
    finally:
        if sqlite:
            with context.autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")
