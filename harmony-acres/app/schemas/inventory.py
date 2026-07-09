import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity_on_hand: int
    low_stock_threshold: int
    updated_at: datetime


class InventorySummaryItem(BaseModel):
    product_id: uuid.UUID
    product_name: str
    quantity_on_hand: int
    low_stock_threshold: int
    is_low_stock: bool
