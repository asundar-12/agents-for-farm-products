import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.product import Product, ProductCategory
from app.schemas.product import ProductAvailability


async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def search_products(
    db: AsyncSession, query: str | None = None, category: ProductCategory | None = None
) -> list[Product]:
    stmt = select(Product)
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if query:
        # Simple substring match — fine for an MVP catalog of ~10 products; would
        # move to a proper full-text/trigram search if the catalog grows.
        stmt = stmt.where(Product.name.ilike(f"%{query}%"))
    result = await db.scalars(stmt)
    return list(result.all())


async def check_availability(db: AsyncSession, product_id: uuid.UUID) -> ProductAvailability:
    product = await get_product_by_id(db, product_id)
    inventory = await db.scalar(select(Inventory).where(Inventory.product_id == product_id))
    quantity_on_hand = inventory.quantity_on_hand if inventory is not None else 0
    return ProductAvailability(
        product_id=product.id,
        name=product.name,
        is_available=product.is_available and quantity_on_hand > 0,
        quantity_on_hand=quantity_on_hand,
    )
