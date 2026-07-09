from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventorySummaryItem


def _row_to_summary(product: Product, inventory: Inventory | None) -> InventorySummaryItem:
    quantity_on_hand = inventory.quantity_on_hand if inventory is not None else 0
    low_stock_threshold = inventory.low_stock_threshold if inventory is not None else 0
    return InventorySummaryItem(
        product_id=product.id,
        product_name=product.name,
        quantity_on_hand=quantity_on_hand,
        low_stock_threshold=low_stock_threshold,
        is_low_stock=quantity_on_hand <= low_stock_threshold,
    )


async def get_inventory_summary(db: AsyncSession) -> list[InventorySummaryItem]:
    # LEFT OUTER JOIN, not INNER: a product with no inventory row yet should still
    # show up (as zero on hand) rather than silently vanishing from the summary.
    stmt = select(Product, Inventory).outerjoin(Inventory, Inventory.product_id == Product.id)
    result = await db.execute(stmt)
    return [_row_to_summary(product, inventory) for product, inventory in result.all()]


async def get_low_stock_items(db: AsyncSession) -> list[InventorySummaryItem]:
    summary = await get_inventory_summary(db)
    return [item for item in summary if item.is_low_stock]
