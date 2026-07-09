"""order totals, refunds, and subscription pause fields

Revision ID: 2f6a1c9d4e7b
Revises: 106ba53d8228
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f6a1c9d4e7b"
down_revision: Union[str, Sequence[str], None] = "106ba53d8228"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # order_items.unit_price: snapshot of the product's price at order time.
    # Backfilled from the current product price for any pre-existing rows so the
    # column can be NOT NULL from here on.
    op.add_column("order_items", sa.Column("unit_price", sa.Numeric(10, 2), nullable=True))
    op.execute(
        """
        UPDATE order_items
        SET unit_price = products.unit_price
        FROM products
        WHERE order_items.product_id = products.id
        """
    )
    op.alter_column("order_items", "unit_price", nullable=False)

    # orders.total_amount: backfilled as the sum of its items' (now-populated) unit_price * quantity.
    op.add_column("orders", sa.Column("total_amount", sa.Numeric(10, 2), nullable=True))
    op.execute(
        """
        UPDATE orders
        SET total_amount = COALESCE(sub.total, 0)
        FROM (
            SELECT order_id, SUM(unit_price * quantity) AS total
            FROM order_items
            GROUP BY order_id
        ) AS sub
        WHERE orders.id = sub.order_id
        """
    )
    op.execute("UPDATE orders SET total_amount = 0 WHERE total_amount IS NULL")
    op.alter_column("orders", "total_amount", nullable=False)

    op.add_column("orders", sa.Column("refund_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("subscriptions", sa.Column("paused_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "paused_until")
    op.drop_column("orders", "refund_amount")
    op.drop_column("orders", "total_amount")
    op.drop_column("order_items", "unit_price")
