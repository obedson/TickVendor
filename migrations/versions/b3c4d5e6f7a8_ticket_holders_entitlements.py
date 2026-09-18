"""Add ticket holders, transfers, entitlements, and self check-in/out state.

Existing tickets keep working: every added column is nullable or carries a server default,
and `purchaser_id` is backfilled from the order that issued the ticket. Historical orders,
payments, tickets, and Impact transactions are never rewritten.
"""
import sqlalchemy as sa
from alembic import op

from src.models.base import GUID

revision = "b3c4d5e6f7a8"
down_revision = "e0f1a2b34567"
branch_labels = None
depends_on = None


def upgrade():
    # Organizer-configured per-order purchase limit; `max_per_user` becomes the per-attendee
    # redemption limit enforced at check-in instead of a purchase cap.
    op.add_column(
        "ticket_types",
        sa.Column("max_per_order", sa.Integer(), nullable=False, server_default="4"),
    )

    with op.batch_alter_table("tickets") as batch:
        batch.add_column(sa.Column("purchaser_id", GUID(), nullable=True))
        batch.add_column(
            sa.Column("assignment_state", sa.String(20), nullable=False, server_default="claimed")
        )
        batch.create_foreign_key(
            "fk_tickets_purchaser_id_users", "users", ["purchaser_id"], ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_tickets_event_holder", "tickets", ["event_id", "attendee_id", "ticket_type_id"]
    )
    # Backfill the durable purchaser record from the issuing order.
    op.execute(
        "UPDATE tickets SET purchaser_id = ("
        "SELECT orders.user_id FROM orders WHERE orders.id = tickets.order_id"
        ") WHERE tickets.order_id IS NOT NULL AND tickets.purchaser_id IS NULL"
    )

    op.add_column("attendances", sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("attendances", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.create_index(
        "ix_attendances_event_checkout", "attendances", ["event_id", "checked_out_at"]
    )

    op.add_column(
        "events", sa.Column("self_check_in_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "events", sa.Column("self_checkout_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("events", sa.Column("checkout_opens_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_events_discovery_ends", "events", ["status", "ends_at"])

    op.create_table(
        "entitlements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("event_id", GUID(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_type_id", GUID(), sa.ForeignKey("ticket_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("redemption_mode", sa.String(12), nullable=False, server_default="either"),
        sa.Column("redemption_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redemption_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_check_in", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_checkout", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_attendance_minutes", sa.Integer(), nullable=True),
        sa.Column("requires_geofence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_staff_validation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("one_time", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_redemptions_per_ticket", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("eligibility", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_entitlement_quantity_nonnegative"),
        sa.CheckConstraint("max_redemptions_per_ticket >= 1", name="ck_entitlement_max_redemptions_positive"),
        sa.CheckConstraint(
            "min_attendance_minutes IS NULL OR min_attendance_minutes >= 0",
            name="ck_entitlement_min_attendance_nonnegative",
        ),
    )
    op.create_index("ix_entitlements_type_active", "entitlements", ["ticket_type_id", "is_active"])
    op.create_index("ix_entitlements_event_active", "entitlements", ["event_id", "is_active"])

    op.create_table(
        "ticket_entitlements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("ticket_id", GUID(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_id", GUID(), sa.ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("quantity_redeemed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(12), nullable=False, server_default="available"),
        sa.Column("last_redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticket_id", "entitlement_id", name="uq_ticket_entitlement"),
        sa.CheckConstraint("quantity_total >= 0", name="ck_ticket_entitlement_total_nonnegative"),
        sa.CheckConstraint("quantity_redeemed >= 0", name="ck_ticket_entitlement_redeemed_nonnegative"),
    )
    op.create_index("ix_ticket_entitlements_ticket_status", "ticket_entitlements", ["ticket_id", "status"])
    op.create_index("ix_ticket_entitlements_entitlement", "ticket_entitlements", ["entitlement_id"])

    op.create_table(
        "entitlement_redemptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("ticket_entitlement_id", GUID(), sa.ForeignKey("ticket_entitlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", GUID(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", GUID(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_id", GUID(), sa.ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holder_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("qr_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="issued"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("redeemed_method", sa.String(12), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entitlement_redemptions_code_status", "entitlement_redemptions", ["code_hash", "status"])
    op.create_index("ix_entitlement_redemptions_event_status", "entitlement_redemptions", ["event_id", "status"])
    op.create_index("ix_entitlement_redemptions_ticket_status", "entitlement_redemptions", ["ticket_id", "status"])

    op.create_table(
        "ticket_transfers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("ticket_id", GUID(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=True),
        sa.Column("recipient_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("claim_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ticket_transfers_ticket_status", "ticket_transfers", ["ticket_id", "status"])
    op.create_index("ix_ticket_transfers_recipient_status", "ticket_transfers", ["recipient_email", "status"])


def downgrade():
    # Redemption, entitlement, transfer, and check-out history has no safe automatic recovery.
    for table in ("entitlement_redemptions", "ticket_entitlements", "entitlements", "ticket_transfers"):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"{table} data exists; plan an explicit recovery before downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM attendances WHERE checked_out_at IS NOT NULL")).scalar():
        raise RuntimeError("Check-out history exists; downgrade would lose attendance duration")

    op.drop_index("ix_ticket_transfers_recipient_status", table_name="ticket_transfers")
    op.drop_index("ix_ticket_transfers_ticket_status", table_name="ticket_transfers")
    op.drop_table("ticket_transfers")
    op.drop_index("ix_entitlement_redemptions_ticket_status", table_name="entitlement_redemptions")
    op.drop_index("ix_entitlement_redemptions_event_status", table_name="entitlement_redemptions")
    op.drop_index("ix_entitlement_redemptions_code_status", table_name="entitlement_redemptions")
    op.drop_table("entitlement_redemptions")
    op.drop_index("ix_ticket_entitlements_entitlement", table_name="ticket_entitlements")
    op.drop_index("ix_ticket_entitlements_ticket_status", table_name="ticket_entitlements")
    op.drop_table("ticket_entitlements")
    op.drop_index("ix_entitlements_event_active", table_name="entitlements")
    op.drop_index("ix_entitlements_type_active", table_name="entitlements")
    op.drop_table("entitlements")

    op.drop_index("ix_events_discovery_ends", table_name="events")
    op.drop_column("events", "checkout_opens_at")
    op.drop_column("events", "self_checkout_enabled")
    op.drop_column("events", "self_check_in_enabled")

    op.drop_index("ix_attendances_event_checkout", table_name="attendances")
    op.drop_column("attendances", "duration_seconds")
    op.drop_column("attendances", "checked_out_at")

    op.drop_index("ix_tickets_event_holder", table_name="tickets")
    op.drop_constraint("fk_tickets_purchaser_id_users", "tickets", type_="foreignkey")
    op.drop_column("tickets", "assignment_state")
    op.drop_column("tickets", "purchaser_id")

    op.drop_column("ticket_types", "max_per_order")
