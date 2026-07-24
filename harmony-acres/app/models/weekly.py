import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.product import Product


class CycleStatus(str, enum.Enum):
    """Lifecycle of the *farm-side* weekly order.

    Deliberately separate from OrderStatus, which tracks an individual
    customer's basket. A customer order goes draft -> submitted and then stops
    moving; everything after that happens to the cycle as a whole, once, for
    every customer at the same time.
    """

    open = "open"  # customers can edit their drafts
    # The plan lists this state and the terminal one both as "closed". They need
    # distinct values (same-valued enum members silently alias in Python), so the
    # deadline-passed state is "locked" and only the archived state is "closed".
    locked = "locked"  # deadline passed, no more edits
    aggregated = "aggregated"  # totals rolled up, waiting on admin review
    approved = "approved"  # admin signed off on the shopping list
    ordered = "ordered"  # admin transcribed it into the farm's own site
    received = "received"  # goods arrived
    closed = "closed"  # archived


class WeeklyCycle(Base):
    """One week of consolidated ordering.

    week_start is the Monday of the week; submission_deadline is the moment
    customer drafts stop being editable. Both are stored rather than derived so
    a cycle can be opened early or its deadline extended without special-casing.
    """

    __tablename__ = "weekly_cycles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CycleStatus] = mapped_column(
        Enum(CycleStatus, name="cycle_status"), nullable=False, default=CycleStatus.open
    )
    # Free-text summary the admin agent generates at aggregation time; null
    # until then.
    admin_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["WeeklyOrderLine"]] = relationship(
        back_populates="cycle", cascade="all, delete-orphan"
    )


class WeeklyOrderLine(Base):
    """One product's total demand for one cycle.

    This is a *snapshot*, not a view: once the admin approves a cycle the
    numbers must stop moving even if an underlying order is somehow edited or a
    subscription changes. Recomputing on read would lose that guarantee.
    """

    __tablename__ = "weekly_order_lines"
    __table_args__ = (UniqueConstraint("cycle_id", "product_id", name="uq_weekly_line_cycle_product"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_cycles.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    # Split so the admin can see how much of the week's demand is standing
    # (subscriptions) versus ad-hoc (one-off orders) — they behave differently
    # when a supplier comes up short.
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subscription_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # An admin override of the total the farm is actually asked for. Null means
    # "no override, order the total_quantity as aggregated." Set when a customer
    # phones in a post-deadline change: their submitted order stays frozen as
    # the record of what they asked for, and only this consolidated number moves.
    # 0 is a real value here (drop the product), which is why null is the
    # "unset" sentinel rather than 0.
    adjusted_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Price at aggregation time, same snapshot rationale as OrderItem.unit_price.
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # What the admin actually managed to buy; null until the cycle is received.
    received_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cycle: Mapped["WeeklyCycle"] = relationship(back_populates="lines")
    # One-directional, same as SubscriptionItem.product — Product has no reason
    # to carry a collection of every weekly line that ever referenced it.
    product: Mapped["Product"] = relationship()

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def product_unit(self) -> str:
        return self.product.unit

    @property
    def effective_quantity(self) -> int:
        """What the farm is actually asked for: the admin override if set, else
        the aggregated total. This is the number that drives cost and the
        default 'received in full' amount."""
        return self.adjusted_quantity if self.adjusted_quantity is not None else self.total_quantity
