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
    """One-shot order creation, used by the AI assistant.

    No order_date field: the order always belongs to the current weekly cycle
    and takes its delivery date from that cycle. Letting a caller name an
    arbitrary date would let them write an order into a week that isn't open.
    """

    items: list[OrderItemCreate]
    note: str | None = None

    @field_validator("items")
    @classmethod
    def _items_must_not_be_empty(cls, value: list[OrderItemCreate]) -> list[OrderItemCreate]:
        if not value:
            raise ValueError("an order must contain at least one item")
        return value


class SetItemQuantity(BaseModel):
    """Absolute quantity for one product in the current draft; 0 removes it."""

    product_id: uuid.UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def _quantity_must_not_be_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("quantity cannot be negative")
        return value


class DraftDetailsUpdate(BaseModel):
    note: str | None = None


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_unit: str
    quantity: int
    unit_price: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID | None
    weekly_cycle_id: uuid.UUID | None
    order_date: date
    status: OrderStatus
    note: str | None
    total_amount: Decimal
    refund_amount: Decimal | None
    submitted_at: datetime | None
    created_at: datetime
    items: list[OrderItemRead]
