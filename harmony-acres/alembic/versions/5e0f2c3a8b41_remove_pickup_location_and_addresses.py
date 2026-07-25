"""remove pickup location and saved addresses

Drops the customer-chosen pickup location from orders and subscriptions, and the
saved-addresses feature (the `addresses` table), which are no longer part of the
product.

Revision ID: 5e0f2c3a8b41
Revises: 4d9e1a2b7c30
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e0f2c3a8b41"
down_revision: Union[str, Sequence[str], None] = "4d9e1a2b7c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("orders", "pickup_location")
    op.drop_column("subscriptions", "pickup_location")
    op.drop_table("addresses")


def downgrade() -> None:
    # Recreate the columns as NOT NULL with an empty-string default so existing
    # rows backfill, then drop the default to match the original schema.
    op.add_column(
        "orders",
        sa.Column("pickup_location", sa.String(), nullable=False, server_default=""),
    )
    op.alter_column("orders", "pickup_location", server_default=None)
    op.add_column(
        "subscriptions",
        sa.Column("pickup_location", sa.String(), nullable=False, server_default=""),
    )
    op.alter_column("subscriptions", "pickup_location", server_default=None)

    op.create_table(
        "addresses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("street", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("zip", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
