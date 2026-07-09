import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.product import ProductCategory
from app.schemas.product import ProductAvailability, ProductRead
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str | None = None,
    category: ProductCategory | None = None,
) -> list[ProductRead]:
    products = await product_service.search_products(db, query=query, category=category)
    return [ProductRead.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> ProductRead:
    product = await product_service.get_product_by_id(db, product_id)
    return ProductRead.model_validate(product)


@router.get("/{product_id}/availability", response_model=ProductAvailability)
async def get_product_availability(
    product_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ProductAvailability:
    return await product_service.check_availability(db, product_id)
