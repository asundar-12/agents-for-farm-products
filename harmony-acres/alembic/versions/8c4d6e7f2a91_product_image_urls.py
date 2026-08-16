"""set product image_url paths for catalog photos

Revision ID: 8c4d6e7f2a91
Revises: 7a2b5c6d1e43
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c4d6e7f2a91"
down_revision: Union[str, Sequence[str], None] = "7a2b5c6d1e43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Static files live under frontend/public/products/ and are served as /products/...
_PRODUCT_IMAGES: dict[str, str] = {
    "Butter (1 lb)": "/products/butter.jpg",
    "Dozen Eggs": "/products/eggs.jpg",
    "Local Honey (12oz)": "/products/honey.jpg",
    "Sourdough Loaf": "/products/sourdough.jpg",
    "Whole Milk (1 Gal)": "/products/milk.jpg",
}


def upgrade() -> None:
    for name, image_url in _PRODUCT_IMAGES.items():
        op.execute(
            f"UPDATE products SET image_url = '{image_url}' WHERE name = '{name}'"
        )


def downgrade() -> None:
    names = ", ".join(f"'{name}'" for name in _PRODUCT_IMAGES)
    op.execute(f"UPDATE products SET image_url = NULL WHERE name IN ({names})")
