import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.customer import User
from app.models.product import Product


class OrderStatus(str, enum.Enum):
    """The customer-facing half of the order lifecycle.

    Only draft -> submitted is live in the weekly-ordering model; everything
    after submission is tracked on the WeeklyCycle, not per-order. The legacy
    per-customer pickup statuses below are retained (not dropped) so rows
    written before the weekly model existed still validate.
    """

    draft = "draft"
    submitted = "submitted"

    # Legacy — no new order is written with these.
    pending = "pending"
    confirmed = "confirmed"
    ready = "ready"
    picked_up = "picked_up"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        # One draft per customer per cycle. A partial index rather than a plain
        # UNIQUE because a customer legitimately has many *submitted* orders
        # historically, and pre-weekly rows have a null cycle_id — both would
        # collide under an unconditional constraint.
        Index(
            "uq_one_draft_per_user_per_cycle",
            "user_id",
            "weekly_cycle_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Nullable: null means this is a one-time order, not generated from a subscription.
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True
    )
    # Nullable only for rows written before the weekly model existed; every new
    # order belongs to exactly one cycle.
    weekly_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_cycles.id"), nullable=True, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.draft
    )
    # Free-text "anything else we should know?" from /order/review. Reaches the
    # admin via the aggregation view, not the shopping list itself.
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Sum of order_items.unit_price * quantity at creation time. Stored (not
    # recomputed from current product prices) so the order's total stays fixed
    # even if a product's price changes later.
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Null until the order is cancelled; then set to whatever was refunded so
    # that history shows both "was cancelled" and "how much came back."
    refund_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    # One-directional: the aggregation view needs each order's customer name,
    # but User has no reason to carry a collection of every order ever placed.
    user: Mapped["User"] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Snapshot of Product.unit_price at the moment the order was placed — locks
    # in what the customer was actually charged, independent of later price changes.
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    # Read-side convenience so order screens can show product names/units
    # without a second round trip. One-directional, like SubscriptionItem.product.
    product: Mapped["Product"] = relationship()

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def product_unit(self) -> str:
        return self.product.unit
