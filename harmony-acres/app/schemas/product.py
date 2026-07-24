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
    unit: str
    image_url: str | None
    is_available: bool
    created_at: datetime


class ProductAvailability(BaseModel):
    """Whether the farm is carrying this product at all.

    In the demand-forwarding model there is no stock on hand to report — we
    forward what customers ask for to the farm rather than fulfilling from our
    own shelves. `quantity_on_hand` is gone rather than pinned at 0, which would
    read as "sold out."
    """

    product_id: uuid.UUID
    name: str
    is_available: bool
