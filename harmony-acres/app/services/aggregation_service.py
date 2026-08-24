"""Rolling a week's demand up into one order.

This is the core of the product: individual customers place small orders, and
the farm receives a single consolidated one. Everything here answers some
version of "what do we buy this week, and who is it for."

Two representations coexist deliberately:

- *Live* demand, recomputed from submitted orders and due subscriptions on
  every read. Correct while a cycle is still moving.
- The *snapshot* in `weekly_order_lines`, written once at aggregation time.
  Once the admin has placed the real order, the numbers have to stop moving
  even if an underlying row somehow changes.

`get_shopping_list` reads the snapshot when one exists and falls back to live
demand when it doesn't, so the admin sees the same list before and after
approving it.
"""

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import User, UserRole
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.subscription import Subscription, SubscriptionItem, SubscriptionStatus
from app.models.weekly import CycleStatus, WeeklyCycle, WeeklyOrderLine
from app.schemas.subscription import SubscriptionRead
from app.schemas.weekly import (
    AdminCustomerSubscriptions,
    AdminSubscriptionsForWeek,
    CustomerBreakdownEntry,
    CycleSummary,
    NonSubmitter,
    ShoppingList,
    ShoppingListLine,
    WeeklyCycleRead,
)
from app.services import cycle_service

# Days between deliveries per frequency. Mirrors subscription_service's table —
# "monthly" is 4 weeks, not a calendar month, so deliveries stay on Wednesdays.
_FREQUENCY_INTERVAL_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 28}

# A line is flagged for a second look when it jumps by at least half AND moves
# at least this many units. The absolute floor is what stops 1 -> 2 dozen eggs
# from screaming +100% at the admin every time a single customer changes a
# small order.
_SPIKE_RATIO = 0.5
_SPIKE_MIN_UNITS = 3

# Aggregation may be re-run while the admin is still reviewing, but not after
# they've signed off — past this point the snapshot is what was actually bought.
_REAGGREGATABLE_STATUSES = (CycleStatus.open, CycleStatus.locked, CycleStatus.aggregated)

# After the farm order is placed, line quantities come from the snapshot so a
# later subscription edit can't move what was already bought. Until then we
# keep using live demand so the customer breakdown and the line totals match.
_FROZEN_STATUSES = (CycleStatus.ordered, CycleStatus.received, CycleStatus.closed)


def subscription_due_in_cycle(subscription: Subscription, cycle: WeeklyCycle) -> bool:
    """Whether this subscription delivers in this cycle.

    Matches on the frequency interval rather than `next_delivery_date == the
    cycle's delivery date`, because nothing advances `next_delivery_date`
    automatically in this MVP. A weekly subscription set up in March would
    otherwise stop counting the moment its stored date fell into the past.
    """
    if subscription.status != SubscriptionStatus.active:
        return False

    days_out = (cycle.delivery_date - subscription.next_delivery_date).days
    if days_out < 0:
        return False  # starts after this week
    interval = _FREQUENCY_INTERVAL_DAYS[subscription.frequency.value]
    return days_out % interval == 0


async def _submitted_orders(db: AsyncSession, cycle: WeeklyCycle) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.weekly_cycle_id == cycle.id, Order.status == OrderStatus.submitted)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.user),
        )
    )
    return list((await db.scalars(stmt)).all())


async def _due_subscriptions(db: AsyncSession, cycle: WeeklyCycle) -> list[Subscription]:
    stmt = (
        select(Subscription)
        .where(Subscription.status == SubscriptionStatus.active)
        .options(
            selectinload(Subscription.items).selectinload(SubscriptionItem.product),
            selectinload(Subscription.user),
        )
    )
    active = list((await db.scalars(stmt)).all())
    return [s for s in active if subscription_due_in_cycle(s, cycle)]


class _Demand:
    """Accumulator for one product's demand across the whole cycle."""

    def __init__(self, product: Product) -> None:
        self.product = product
        self.order_quantity = 0
        self.subscription_quantity = 0
        self.customers: list[CustomerBreakdownEntry] = []

    @property
    def total_quantity(self) -> int:
        return self.order_quantity + self.subscription_quantity

    def add(self, user: User, quantity: int, source: str) -> None:
        if source == "order":
            self.order_quantity += quantity
        else:
            self.subscription_quantity += quantity

        # Merge on (customer, source): a customer can hold two subscriptions
        # that both include eggs, and the admin dividing up a short delivery
        # needs one number per person, not one row per subscription. Order and
        # subscription demand stay separate because they aren't equally
        # negotiable when supply falls short.
        for entry in self.customers:
            if entry.user_id == user.id and entry.source == source:
                entry.quantity += quantity
                return

        self.customers.append(
            CustomerBreakdownEntry(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                quantity=quantity,
                source=source,
            )
        )


async def collect_demand(db: AsyncSession, cycle: WeeklyCycle) -> dict[uuid.UUID, _Demand]:
    """Live per-product demand for a cycle, keyed by product id."""
    demand: dict[uuid.UUID, _Demand] = {}

    def bucket(product: Product) -> _Demand:
        if product.id not in demand:
            demand[product.id] = _Demand(product)
        return demand[product.id]

    for order in await _submitted_orders(db, cycle):
        for item in order.items:
            bucket(item.product).add(order.user, item.quantity, "order")

    for subscription in await _due_subscriptions(db, cycle):
        for item in subscription.items:
            bucket(item.product).add(subscription.user, item.quantity, "subscription")

    return demand


async def aggregate_cycle(db: AsyncSession, cycle: WeeklyCycle) -> WeeklyCycle:
    """Freeze this cycle's demand into `weekly_order_lines`.

    Replaces any existing lines rather than merging, so re-running after a late
    change produces a clean snapshot instead of doubled quantities.
    """
    if cycle.status not in _REAGGREGATABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot re-aggregate a cycle that is already '{cycle.status.value}'",
        )

    demand = await collect_demand(db, cycle)

    existing = list(
        (await db.scalars(select(WeeklyOrderLine).where(WeeklyOrderLine.cycle_id == cycle.id))).all()
    )
    for line in existing:
        await db.delete(line)
    await db.flush()

    for product_id, entry in demand.items():
        db.add(
            WeeklyOrderLine(
                cycle_id=cycle.id,
                product_id=product_id,
                order_quantity=entry.order_quantity,
                subscription_quantity=entry.subscription_quantity,
                total_quantity=entry.total_quantity,
                unit_price=Decimal(str(entry.product.unit_price)),
            )
        )

    cycle.status = CycleStatus.aggregated
    await db.commit()
    return await cycle_service.get_cycle_with_lines(db, cycle.id)


async def _previous_totals(db: AsyncSession, cycle: WeeklyCycle) -> dict[uuid.UUID, int]:
    """Prior cycle's per-product totals, for week-over-week deltas.

    Looks at the most recent *earlier* cycle. Prefers a frozen snapshot; if
    that week was never aggregated, falls back to live `collect_demand` so
    deltas still work.
    """
    stmt = (
        select(WeeklyCycle)
        .where(WeeklyCycle.week_start < cycle.week_start)
        .order_by(WeeklyCycle.week_start.desc())
        .options(selectinload(WeeklyCycle.lines))
    )
    previous = (await db.scalars(stmt)).first()
    if previous is None:
        return {}
    if previous.lines:
        return {line.product_id: line.total_quantity for line in previous.lines}
    live = await collect_demand(db, previous)
    return {product_id: entry.total_quantity for product_id, entry in live.items()}


def _movement(total: int, previous: int | None) -> tuple[int | None, float | None, bool]:
    """Delta, percent change, and whether it counts as a spike."""
    if previous is None:
        return None, None, False

    delta = total - previous
    # Growth from zero has no meaningful percentage. Treat it as a spike purely
    # on the absolute move so a brand-new product still gets a second look.
    if previous == 0:
        return delta, None, delta >= _SPIKE_MIN_UNITS

    pct = delta / previous
    is_spike = pct >= _SPIKE_RATIO and delta >= _SPIKE_MIN_UNITS
    return delta, round(pct * 100, 1), is_spike


async def get_shopping_list(db: AsyncSession, cycle_id: uuid.UUID) -> ShoppingList:
    """The admin's buy list: what, how much, for whom, and what moved.

    Takes an id rather than a cycle because it has to load the cycle with its
    lines eagerly anyway — passing an already-loaded cycle would just mean
    fetching it twice.
    """
    cycle = await cycle_service.get_cycle_with_lines(db, cycle_id)
    demand = await collect_demand(db, cycle)
    previous = await _previous_totals(db, cycle)
    snapshot = {line.product_id: line for line in cycle.lines}
    frozen = cycle.status in _FROZEN_STATUSES

    # Live demand while the week is still moving, so line totals match the
    # expanded customer rows. The snapshot once the farm order is placed, or
    # when there is no live demand (a test/admin snapshot with no orders).
    product_ids = set(demand)
    if frozen or not product_ids:
        product_ids |= set(snapshot)

    lines: list[ShoppingListLine] = []
    total_cost = Decimal("0")
    for product_id in product_ids:
        live = demand.get(product_id)
        snap = snapshot.get(product_id)
        product = live.product if live is not None else snap.product
        customers = list(live.customers) if live is not None else []

        if live is not None and not frozen:
            order_qty = live.order_quantity
            sub_qty = live.subscription_quantity
            total_qty = live.total_quantity
            unit_price = Decimal(str(product.unit_price))
        elif snap is not None:
            order_qty = snap.order_quantity
            sub_qty = snap.subscription_quantity
            total_qty = snap.total_quantity
            unit_price = Decimal(str(snap.unit_price))
        else:
            continue

        adjusted_qty = snap.adjusted_quantity if snap is not None else None
        effective_qty = adjusted_qty if adjusted_qty is not None else total_qty
        line_total = unit_price * effective_qty
        total_cost += line_total
        # Deltas track real demand, not the admin's override — a spike means
        # customers asked for more, so the comparison is always total vs total.
        prev = previous.get(product.id)
        delta, delta_pct, is_spike = _movement(total_qty, prev)
        lines.append(
            ShoppingListLine(
                product_id=product.id,
                product_name=product.name,
                product_unit=product.unit,
                category=product.category.value,
                unit_price=unit_price,
                order_quantity=order_qty,
                subscription_quantity=sub_qty,
                total_quantity=total_qty,
                adjusted_quantity=adjusted_qty,
                effective_quantity=effective_qty,
                line_total=line_total,
                previous_total=prev,
                delta=delta,
                delta_pct=delta_pct,
                is_spike=is_spike,
                customers=sorted(customers, key=lambda c: (-c.quantity, c.full_name)),
            )
        )

    # Category then name: the farm's own order form is grouped that way, and
    # the admin transcribes this list into it by hand.
    lines.sort(key=lambda line: (line.category, line.product_name))

    customer_ids = {entry.user_id for line in lines for entry in line.customers}

    return ShoppingList(
        cycle=WeeklyCycleRead.model_validate(cycle),
        lines=lines,
        total_cost=total_cost,
        customer_count=len(customer_ids),
        order_count=sum(line.order_quantity for line in lines),
        subscription_count=sum(line.subscription_quantity for line in lines),
    )


async def list_non_submitters(db: AsyncSession, cycle: WeeklyCycle) -> list[NonSubmitter]:
    """Customers with nothing coming this week, so the admin can nudge them."""
    orders = await _submitted_orders(db, cycle)
    subscriptions = await _due_subscriptions(db, cycle)
    covered = {o.user_id for o in orders} | {s.user_id for s in subscriptions}

    customers = list(
        (
            await db.scalars(
                select(User).where(User.role == UserRole.customer).order_by(User.full_name)
            )
        ).all()
    )

    drafts = list(
        (
            await db.scalars(
                select(Order)
                .where(Order.weekly_cycle_id == cycle.id, Order.status == OrderStatus.draft)
                .options(selectinload(Order.items))
            )
        ).all()
    )
    drafts_by_user = {d.user_id: d for d in drafts}

    result: list[NonSubmitter] = []
    for customer in customers:
        if customer.id in covered:
            continue
        draft = drafts_by_user.get(customer.id)
        result.append(
            NonSubmitter(
                user_id=customer.id,
                full_name=customer.full_name,
                email=customer.email,
                has_draft=draft is not None and len(draft.items) > 0,
                draft_item_count=len(draft.items) if draft is not None else 0,
            )
        )
    return result


async def record_received(
    db: AsyncSession, cycle: WeeklyCycle, received: dict[uuid.UUID, int] | None
) -> None:
    """Record what actually arrived against each line.

    `None` means everything came in as ordered, which is the common case — each
    line's received quantity is set to what was asked for. A partial dict only
    overrides the products named, so the admin reports shortfalls rather than
    retyping the whole delivery.
    """
    lines = list(
        (await db.scalars(select(WeeklyOrderLine).where(WeeklyOrderLine.cycle_id == cycle.id))).all()
    )
    unknown = set(received or {}) - {line.product_id for line in lines}
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{len(unknown)} product(s) in this report aren't on the week's order",
        )

    for line in lines:
        # Default to what was actually ordered — the admin's override if they
        # set one, otherwise the aggregated total. "Everything arrived" means
        # the adjusted amount arrived, not the pre-adjustment demand.
        default = line.effective_quantity
        if received is None:
            line.received_quantity = default
        else:
            line.received_quantity = received.get(line.product_id, default)


async def set_line_quantity(
    db: AsyncSession, cycle: WeeklyCycle, product_id: uuid.UUID, quantity: int | None
) -> None:
    """Override (or clear) the quantity to actually order for one product.

    Only meaningful on an aggregated line, and only before the order is placed
    with the farm — after 'ordered' the number is a matter of record, not a
    plan. Customer orders are untouched; this moves only the consolidated total.
    """
    if cycle.status not in (CycleStatus.aggregated, CycleStatus.approved):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Line quantities can only be adjusted after aggregation and "
                "before the order is placed with the farm."
            ),
        )

    line = await db.scalar(
        select(WeeklyOrderLine).where(
            WeeklyOrderLine.cycle_id == cycle.id, WeeklyOrderLine.product_id == product_id
        )
    )
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That product isn't on this week's order"
        )

    line.adjusted_quantity = quantity
    await db.commit()


async def get_cycle_summary(db: AsyncSession, cycle_id: uuid.UUID) -> CycleSummary:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    shopping_list = await get_shopping_list(db, cycle_id)
    non_submitters = await list_non_submitters(db, cycle)

    return CycleSummary(
        cycle=shopping_list.cycle,
        total_cost=shopping_list.total_cost,
        product_count=len(shopping_list.lines),
        total_units=sum(line.total_quantity for line in shopping_list.lines),
        customer_count=shopping_list.customer_count,
        order_count=shopping_list.order_count,
        subscription_count=shopping_list.subscription_count,
        non_submitter_count=len(non_submitters),
        spike_count=sum(1 for line in shopping_list.lines if line.is_spike),
    )


async def list_due_subscriptions_by_customer(
    db: AsyncSession, cycle: WeeklyCycle
) -> AdminSubscriptionsForWeek:
    """Active subscriptions due in this cycle, grouped by customer (admin included)."""
    due = await _due_subscriptions(db, cycle)
    by_user: dict[uuid.UUID, list[Subscription]] = {}
    users: dict[uuid.UUID, User] = {}
    for subscription in due:
        by_user.setdefault(subscription.user_id, []).append(subscription)
        users[subscription.user_id] = subscription.user

    customers = []
    for user_id, subs in sorted(by_user.items(), key=lambda kv: users[kv[0]].full_name.lower()):
        user = users[user_id]
        customers.append(
            AdminCustomerSubscriptions(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                subscriptions=[SubscriptionRead.model_validate(s) for s in subs],
            )
        )

    return AdminSubscriptionsForWeek(
        cycle=WeeklyCycleRead.model_validate(cycle),
        customers=customers,
    )
