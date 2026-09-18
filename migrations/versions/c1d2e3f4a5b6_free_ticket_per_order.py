"""Hold free ticket types to one ticket per order.

A price of zero is not a sale, so one buyer has nothing legitimate to gain by taking the whole
allocation in a single checkout. Types created or edited through the API are normalized by the
service; this brings the rows that already exist into line, so what a listing reports and what the
purchase behind it allows are the same number.

Only forward-looking configuration moves, and it moves down to a ceiling the purchase path already
enforces. Issued tickets, orders, payments, and Impact history are untouched.
"""
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    # Free and above the ceiling, and nothing else: a paid type's organizer-configured limit is
    # theirs to keep, and a free type already at one is already correct.
    op.execute("UPDATE ticket_types SET max_per_order = 1 WHERE price = 0 AND max_per_order > 1")


def downgrade():
    # The previous number is not recorded anywhere and cannot be invented; one is a valid ceiling
    # for any ticket type, so rolling back leaves every row releasable rather than guessing values
    # back into place.
    pass
