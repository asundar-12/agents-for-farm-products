"""one line per product per subscription

Revision ID: 7a2b5c6d1e43
Revises: 6f1a3d4b0c52
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a2b5c6d1e43"
down_revision: Union[str, Sequence[str], None] = "6f1a3d4b0c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_subscription_item_product", "subscription_items", ["subscription_id", "product_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_subscription_item_product", "subscription_items", type_="unique")
