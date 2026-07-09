import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.product import ProductCategory


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: ProductCategory
    description: str | None
    unit_price: Decimal
    is_available: bool
    created_at: datetime


class ProductAvailability(BaseModel):
    product_id: uuid.UUID
    name: str
    is_available: bool
    quantity_on_hand: int
