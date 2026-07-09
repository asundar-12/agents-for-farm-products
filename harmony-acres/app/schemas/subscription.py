import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.subscription import SubscriptionFrequency, SubscriptionStatus


class SubscriptionItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def _quantity_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("quantity must be at least 1")
        return value


class SubscriptionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int


class SubscriptionCreate(BaseModel):
    pickup_location: str
    frequency: SubscriptionFrequency
    next_delivery_date: date
    items: list[SubscriptionItemCreate]

    @field_validator("items")
    @classmethod
    def _items_must_not_be_empty(cls, value: list[SubscriptionItemCreate]) -> list[SubscriptionItemCreate]:
        if not value:
            raise ValueError("a subscription must contain at least one item")
        return value


class SubscriptionUpdate(BaseModel):
    frequency: SubscriptionFrequency | None = None
    items: list[SubscriptionItemCreate] | None = None


class SubscriptionPause(BaseModel):
    resume_on: date | None = None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    pickup_location: str
    frequency: SubscriptionFrequency
    next_delivery_date: date
    status: SubscriptionStatus
    paused_until: date | None
    created_at: datetime
    updated_at: datetime
    items: list[SubscriptionItemRead]
