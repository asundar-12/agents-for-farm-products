"""admin override on weekly order lines

Revision ID: 4d9e1a2b7c30
Revises: 3c8d2b5f9a10
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d9e1a2b7c30"
down_revision: Union[str, Sequence[str], None] = "3c8d2b5f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with no default: null means "no admin override, order the
    # aggregated total." 0 is a legitimate value (drop the product), so it
    # can't double as the unset sentinel.
    op.add_column("weekly_order_lines", sa.Column("adjusted_quantity", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("weekly_order_lines", "adjusted_quantity")
