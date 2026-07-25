import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.weekly import WeeklyCycle
from app.schemas.order import OrderCreate
from app.services import cycle_service

# Legacy per-pickup statuses that predate the weekly model. Kept only so old
# rows remain cancellable; nothing new is written with them.
_CANCELLABLE_STATUSES = (OrderStatus.draft, OrderStatus.pending, OrderStatus.confirmed)


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    order = await db.scalar(stmt)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def assert_owned_by(order: Order, user_id: uuid.UUID) -> None:
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")


async def list_orders_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.order_date.desc())
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_upcoming_orders_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Order]:
    stmt = (
        select(Order)
        .where(
            Order.user_id == user_id,
            Order.order_date >= date.today(),
            Order.status != OrderStatus.cancelled,
        )
        .order_by(Order.order_date.asc())
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    result = await db.scalars(stmt)
    return list(result.all())


# --- Draft lifecycle ---------------------------------------------------------


async def get_or_create_draft(db: AsyncSession, user_id: uuid.UUID, cycle: WeeklyCycle) -> Order:
    """The customer's basket for this cycle, created empty on first touch.

    Every ordering screen calls this, including read-only ones — a customer who
    only browses ends up with an empty draft that is simply never submitted,
    which costs one row and saves the client from having to distinguish "no
    draft yet" from "empty draft" on every request.

    Refuses once the customer has already submitted for this cycle. The unique
    index only covers drafts, so without this check a customer could submit,
    be handed a brand-new draft, and submit a second order into the same week —
    which would double-count them in the aggregation.
    """
    submitted = await get_submitted_order_for_cycle(db, user_id, cycle.id)
    if submitted is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You've already submitted your order for this week. Contact the farm to change it.",
        )

    stmt = (
        select(Order)
        .where(
            Order.user_id == user_id,
            Order.weekly_cycle_id == cycle.id,
            Order.status == OrderStatus.draft,
        )
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    draft = await db.scalar(stmt)
    if draft is not None:
        return draft

    draft = Order(
        user_id=user_id,
        weekly_cycle_id=cycle.id,
        order_date=cycle.delivery_date,
        status=OrderStatus.draft,
        total_amount=Decimal("0"),
    )
    db.add(draft)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race against a concurrent request for the same user+cycle; the
        # partial unique index rejected the second insert. Read the winner.
        await db.rollback()
        draft = await db.scalar(stmt)
        if draft is None:  # pragma: no cover - only reachable if the index vanished
            raise
        return draft
    return await get_order_by_id(db, draft.id)


def _recalculate_total(order: Order) -> None:
    order.total_amount = sum(
        (Decimal(str(item.unit_price)) * item.quantity for item in order.items), Decimal("0")
    )


async def set_item_quantity(
    db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> Order:
    """Set one product's quantity in the current draft; 0 removes it.

    An absolute upsert rather than add/remove because this backs a +/- stepper:
    the client knows the quantity it wants, not whether a row already exists,
    and sending an absolute value makes retries and out-of-order responses
    harmless — which the debounced optimistic UI depends on.
    """
    if quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="quantity cannot be negative"
        )

    cycle = await cycle_service.get_or_create_current_cycle(db)
    cycle_service.assert_open(cycle)

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if quantity > 0 and not product.is_available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{product.name}' isn't being carried this week",
        )

    draft = await get_or_create_draft(db, user_id, cycle)
    existing = next((item for item in draft.items if item.product_id == product_id), None)

    if quantity == 0:
        if existing is not None:
            draft.items.remove(existing)
    elif existing is not None:
        existing.quantity = quantity
        # Re-snapshot the price: nothing is committed while the draft is open,
        # so the customer should see and pay today's price.
        existing.unit_price = Decimal(str(product.unit_price))
    else:
        draft.items.append(
            OrderItem(
                product_id=product_id,
                quantity=quantity,
                unit_price=Decimal(str(product.unit_price)),
            )
        )

    await db.flush()
    _recalculate_total(draft)
    await db.commit()
    return await get_order_by_id(db, draft.id)


async def set_draft_details(
    db: AsyncSession,
    user_id: uuid.UUID,
    note: str | None = None,
) -> Order:
    cycle = await cycle_service.get_or_create_current_cycle(db)
    cycle_service.assert_open(cycle)
    draft = await get_or_create_draft(db, user_id, cycle)

    if note is not None:
        draft.note = note

    await db.commit()
    return await get_order_by_id(db, draft.id)


async def submit_order(db: AsyncSession, user_id: uuid.UUID) -> Order:
    """Commit the current draft into this week's consolidated order.

    One-way on purpose: there's no un-submit, because by the time a customer
    changes their mind the admin may already have placed the real order with the
    farm. Changes after this go through the admin.
    """
    cycle = await cycle_service.get_or_create_current_cycle(db)
    cycle_service.assert_open(cycle)
    draft = await get_or_create_draft(db, user_id, cycle)

    if not draft.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add at least one item before submitting your order",
        )

    _recalculate_total(draft)
    draft.status = OrderStatus.submitted
    draft.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_order_by_id(db, draft.id)


async def get_submitted_order_for_cycle(
    db: AsyncSession, user_id: uuid.UUID, cycle_id: uuid.UUID
) -> Order | None:
    stmt = (
        select(Order)
        .where(
            Order.user_id == user_id,
            Order.weekly_cycle_id == cycle_id,
            Order.status == OrderStatus.submitted,
        )
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    return await db.scalar(stmt)


async def get_current_order(db: AsyncSession, user_id: uuid.UUID, cycle: WeeklyCycle) -> Order:
    """This week's order for the customer, submitted or still a draft.

    The read path, as opposed to get_or_create_draft's write path: screens need
    to render the submitted order read-only rather than get a 422, so this
    returns whatever exists and only falls back to creating a draft when the
    customer hasn't submitted yet.
    """
    submitted = await get_submitted_order_for_cycle(db, user_id, cycle.id)
    if submitted is not None:
        return submitted
    return await get_or_create_draft(db, user_id, cycle)


# --- One-shot creation -------------------------------------------------------


async def create_order(db: AsyncSession, user_id: uuid.UUID, data: OrderCreate) -> Order:
    """Create and immediately submit an order in a single call.

    The UI drives ordering through the draft flow instead; this exists for the
    AI assistant, where "order 2 gallons of milk for this week" is one utterance
    and a draft round-trip would add nothing.
    """
    cycle = await cycle_service.get_or_create_current_cycle(db)
    cycle_service.assert_open(cycle)

    # Same one-order-per-week rule the draft flow enforces — the assistant path
    # writes a submitted order directly, so it needs its own check.
    existing = await get_submitted_order_for_cycle(db, user_id, cycle.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You've already submitted your order for this week. Contact the farm to change it.",
        )

    total_amount = Decimal("0")
    order_items: list[OrderItem] = []

    for item in data.items:
        product = await db.get(Product, item.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item.product_id} not found"
            )
        # No stock check: Farm Product Agent forwards demand to the farm rather than
        # fulfilling from its own shelves, so the only question is whether the
        # farm carries the item at all.
        if not product.is_available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{product.name}' isn't being carried this week",
            )

        unit_price = Decimal(str(product.unit_price))
        total_amount += unit_price * item.quantity
        order_items.append(OrderItem(product_id=product.id, quantity=item.quantity, unit_price=unit_price))

    order = Order(
        user_id=user_id,
        weekly_cycle_id=cycle.id,
        order_date=cycle.delivery_date,
        status=OrderStatus.submitted,
        submitted_at=datetime.now(timezone.utc),
        note=data.note,
        total_amount=total_amount,
        items=order_items,
    )
    db.add(order)
    await db.commit()
    return await get_order_by_id(db, order.id)


async def cancel_order(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    """Cancel an order that hasn't been forwarded to the farm yet.

    Once the cycle locks, the order is part of a consolidated purchase that has
    probably already been placed, so cancelling stops being the customer's call.
    """
    order = await get_order_by_id(db, order_id)
    assert_owned_by(order, user_id)

    if order.status == OrderStatus.submitted:
        if order.weekly_cycle_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This order can no longer be cancelled",
            )
        cycle = await cycle_service.get_cycle_by_id(db, order.weekly_cycle_id)
        cycle_service.assert_open(cycle)
    elif order.status not in _CANCELLABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Order cannot be cancelled once it is '{order.status.value}'",
        )

    # No inventory to restore — nothing was ever decremented.
    order.status = OrderStatus.cancelled
    order.refund_amount = order.total_amount
    await db.commit()
    return await get_order_by_id(db, order.id)
