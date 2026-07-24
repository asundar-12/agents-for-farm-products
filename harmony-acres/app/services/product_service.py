import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Whether the farm is carrying this product this season.

    Kept its name through the shift to demand-forwarding, but the meaning
    narrowed: there is no stock on hand to count, only whether the item is on
    offer at all.
    """
    product = await get_product_by_id(db, product_id)
    return ProductAvailability(
        product_id=product.id,
        name=product.name,
        is_available=product.is_available,
    )
