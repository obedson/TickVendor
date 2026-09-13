"""External identities without changing existing user IDs, passwords or roles."""
import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision = "d9e0f1a23456"
down_revision = "c8d9e0f12345"
branch_labels = None
depends_on = None


def upgrade():
    context = op.get_context()
    sqlite = context.dialect.name == "sqlite"
    if sqlite:
        # SQLite cannot rebuild a referenced table with FK enforcement enabled.
        # Change the connection-local pragma outside a transaction, never globally.
        with context.autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("users") as batch:
            batch.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
        if sqlite and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first():
            raise RuntimeError("Foreign-key integrity check failed after users rebuild")
    finally:
        if sqlite:
            with context.autocommit_block():
                op.execute("PRAGMA foreign_keys=ON")
    op.create_table("external_identities",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_external_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_external_provider"))
    op.create_table("google_auth_flows",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("state_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("handoff_challenge", sa.String(43), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("callback_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("handoff_hash", sa.String(64), unique=True),
        sa.Column("provider_subject", sa.String(255)),
        sa.Column("provider_email", sa.String(320)),
        sa.Column("provider_name", sa.String(120)),
        sa.Column("link_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_google_auth_flows_expires_at", "google_auth_flows", ["expires_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM external_identities")).scalar():
        raise RuntimeError("Google identities exist: disable Google and plan identity-preserving recovery before downgrade")
    # Keep nullable passwords: Google-only accounts must not be deleted or assigned dummy hashes.
    # This is a data-shape downgrade, not permission to run old password-only code on Google-only users.
    op.drop_index("ix_google_auth_flows_expires_at", "google_auth_flows")
    op.drop_table("google_auth_flows")
    op.drop_table("external_identities")
