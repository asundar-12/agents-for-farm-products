"""weekly cycles, draft orders, product unit/image

Revision ID: 3c8d2b5f9a10
Revises: 2f6a1c9d4e7b
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c8d2b5f9a10"
down_revision: Union[str, Sequence[str], None] = "2f6a1c9d4e7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- products: card fields ---
    # unit is NOT NULL with a server_default so existing rows backfill to "each"
    # without a separate UPDATE. The default stays on the column: it's a
    # sensible value for countable goods, not just a migration crutch.
    op.add_column("products", sa.Column("unit", sa.String(), nullable=False, server_default="each"))
    op.add_column("products", sa.Column("image_url", sa.String(), nullable=True))

    # --- order_status: add draft/submitted ---
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on older
    # Postgres, and Alembic wraps each migration in one. autocommit_block()
    # steps outside it for exactly these statements.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'draft'")
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'submitted'")

    cycle_status = postgresql.ENUM(
        "open",
        "locked",
        "aggregated",
        "approved",
        "ordered",
        "received",
        "closed",
        name="cycle_status",
    )
    cycle_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "weekly_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        # create_type=False: the type was just created above, don't let the
        # column definition try to CREATE TYPE a second time.
        sa.Column("status", postgresql.ENUM(name="cycle_status", create_type=False), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_weekly_cycles_week_start", "weekly_cycles", ["week_start"], unique=True)

    op.create_table(
        "weekly_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weekly_cycles.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("order_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subscription_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=True),
        sa.UniqueConstraint("cycle_id", "product_id", name="uq_weekly_line_cycle_product"),
    )
    op.create_index("ix_weekly_order_lines_cycle_id", "weekly_order_lines", ["cycle_id"])

    # --- orders: cycle link, note, submitted_at ---
    op.add_column(
        "orders",
        sa.Column(
            "weekly_cycle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weekly_cycles.id"), nullable=True
        ),
    )
    op.create_index("ix_orders_weekly_cycle_id", "orders", ["weekly_cycle_id"])
    op.add_column("orders", sa.Column("note", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))

    # Partial unique index: a customer may hold at most one draft per cycle, but
    # any number of submitted orders. Legacy rows have status/cycle_id outside
    # this predicate and are unaffected.
    op.create_index(
        "uq_one_draft_per_user_per_cycle",
        "orders",
        ["user_id", "weekly_cycle_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index("uq_one_draft_per_user_per_cycle", table_name="orders")
    op.drop_column("orders", "submitted_at")
    op.drop_column("orders", "note")
    op.drop_index("ix_orders_weekly_cycle_id", table_name="orders")
    op.drop_column("orders", "weekly_cycle_id")

    op.drop_index("ix_weekly_order_lines_cycle_id", table_name="weekly_order_lines")
    op.drop_table("weekly_order_lines")
    op.drop_index("ix_weekly_cycles_week_start", table_name="weekly_cycles")
    op.drop_table("weekly_cycles")
    postgresql.ENUM(name="cycle_status").drop(op.get_bind(), checkfirst=True)

    op.drop_column("products", "image_url")
    op.drop_column("products", "unit")

    # Postgres has no ALTER TYPE ... DROP VALUE. Removing 'draft'/'submitted'
    # means recreating order_status without them, which would fail while any row
    # still uses them — so this downgrade deliberately leaves the two values in
    # place. They're inert once nothing references them.
