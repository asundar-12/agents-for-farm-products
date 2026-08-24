import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.weekly import CycleStatus
from app.schemas.subscription import SubscriptionRead


class WeeklyCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    week_start: date
    submission_deadline: datetime
    delivery_date: date
    status: CycleStatus
    admin_notes: str | None
    approved_at: datetime | None
    ordered_at: datetime | None
    received_at: datetime | None
    created_at: datetime


class WeeklyCycleSummary(BaseModel):
    """What the customer needs to know about the current week.

    Every customer-facing screen keys its "can I still edit?" state off
    `is_open` rather than re-deriving it from the deadline, so the lock lands
    everywhere at once.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    week_start: date
    submission_deadline: datetime
    delivery_date: date
    status: CycleStatus
    is_open: bool


class WeeklyOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_unit: str
    order_quantity: int
    subscription_quantity: int
    total_quantity: int
    unit_price: Decimal
    received_quantity: int | None


class CustomerBreakdownEntry(BaseModel):
    """One customer's share of a single product's weekly total.

    The admin needs this when the farm comes up short: knowing 40 dozen eggs
    are wanted is useless for deciding who gets the 30 that arrived.
    """

    user_id: uuid.UUID
    full_name: str
    email: str
    quantity: int
    source: str  # "order" | "subscription"


class ShoppingListLine(BaseModel):
    product_id: uuid.UUID
    product_name: str
    product_unit: str
    category: str
    unit_price: Decimal
    order_quantity: int
    subscription_quantity: int
    total_quantity: int
    # Admin override of the total to actually order; null when untouched.
    adjusted_quantity: int | None
    # total_quantity, or adjusted_quantity when the admin has overridden it.
    # This is what line_total and the buy quantity are based on.
    effective_quantity: int
    line_total: Decimal
    # Week-over-week movement. Null when there's no prior cycle to compare
    # against — distinct from 0, which means "same as last week".
    previous_total: int | None
    delta: int | None
    delta_pct: float | None
    is_spike: bool
    customers: list[CustomerBreakdownEntry]


class ShoppingList(BaseModel):
    cycle: WeeklyCycleRead
    lines: list[ShoppingListLine]
    total_cost: Decimal
    # Unique people who appear on any line (order and/or subscription).
    customer_count: int
    # Unit totals from the lines — the same numbers as summing
    # `order_quantity` / `subscription_quantity` across products, so the
    # headline strip matches the expanded customer rows.
    order_count: int
    subscription_count: int


class NonSubmitter(BaseModel):
    """A customer with nothing coming this week.

    Includes anyone with neither a submitted order nor a subscription due, so
    the admin can nudge them before the deadline. `has_draft` separates "forgot
    to hit submit" from "hasn't looked at it" — the first is worth a reminder.
    """

    user_id: uuid.UUID
    full_name: str
    email: str
    has_draft: bool
    draft_item_count: int


class ReceivedLine(BaseModel):
    """What actually turned up, per product."""

    product_id: uuid.UUID
    received_quantity: int


class MarkReceivedRequest(BaseModel):
    """Optional shortfall reporting when goods arrive.

    Omitting `lines` means everything arrived as ordered — the common case, and
    not worth making the admin retype the whole list to say so.
    """

    lines: list[ReceivedLine] | None = None


class AdminNotesUpdate(BaseModel):
    admin_notes: str | None = None


class SetLineQuantity(BaseModel):
    """Admin override of a shopping-list line's order quantity.

    Absolute, not a delta — the admin types the number to actually order. null
    clears the override and reverts to the aggregated total.
    """

    quantity: int | None

    @field_validator("quantity")
    @classmethod
    def _not_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("quantity cannot be negative")
        return value


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    created_at: datetime


class CycleSummary(BaseModel):
    """Headline numbers for the admin dashboard."""

    cycle: WeeklyCycleRead
    total_cost: Decimal
    product_count: int
    total_units: int
    customer_count: int
    order_count: int
    subscription_count: int
    non_submitter_count: int
    spike_count: int


class AdminCustomerSubscriptions(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    subscriptions: list[SubscriptionRead]


class AdminSubscriptionsForWeek(BaseModel):
    cycle: WeeklyCycleRead
    customers: list[AdminCustomerSubscriptions]
