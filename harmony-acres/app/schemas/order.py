import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def _quantity_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("quantity must be at least 1")
        return value


class OrderCreate(BaseModel):
    pickup_location: str
    order_date: date
    items: list[OrderItemCreate]

    @field_validator("items")
    @classmethod
    def _items_must_not_be_empty(cls, value: list[OrderItemCreate]) -> list[OrderItemCreate]:
        if not value:
            raise ValueError("an order must contain at least one item")
        return value


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID | None
    pickup_location: str
    order_date: date
    status: OrderStatus
    total_amount: Decimal
    refund_amount: Decimal | None
    created_at: datetime
    items: list[OrderItemRead]
