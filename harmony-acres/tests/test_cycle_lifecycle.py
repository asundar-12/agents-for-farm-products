"""Weekly cycle lifecycle transitions (business rule 1, the farm-side workflow).

The cycle is where the Approved -> Ordered -> Received -> Closed states actually
live. cycle_service.transition() is the single gate; it encodes the legal moves
as data, so calling steps out of order must fail rather than silently jump.

Full legal path: open -> locked -> aggregated -> approved -> ordered -> received
-> closed, plus two legal step-backs (locked->open, aggregated<-approved reject).
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.order import Order
from app.models.weekly import CycleStatus, WeeklyOrderLine
from app.services import cycle_service
from tests.factories import make_cycle, make_product, make_submitted_order, make_user


async def _snapshot_line_count(db, cycle_id) -> int:
    rows = await db.scalars(select(WeeklyOrderLine).where(WeeklyOrderLine.cycle_id == cycle_id))
    return len(rows.all())


async def _add_snapshot_line(db, cycle, product) -> None:
    db.add(
        WeeklyOrderLine(
            cycle_id=cycle.id,
            product_id=product.id,
            order_quantity=1,
            subscription_quantity=0,
            total_quantity=1,
            unit_price=Decimal("1.00"),
        )
    )
    await db.commit()


# --- Valid transitions -------------------------------------------------------


@pytest.mark.parametrize(
    "start,target",
    [
        (CycleStatus.open, CycleStatus.locked),
        (CycleStatus.locked, CycleStatus.aggregated),
        (CycleStatus.locked, CycleStatus.open),
        (CycleStatus.aggregated, CycleStatus.approved),
        (CycleStatus.aggregated, CycleStatus.locked),
        (CycleStatus.approved, CycleStatus.ordered),
        (CycleStatus.approved, CycleStatus.aggregated),  # reject back for review
        (CycleStatus.ordered, CycleStatus.received),
        (CycleStatus.received, CycleStatus.closed),
    ],
)
async def test_valid_transition_updates_state(db, start, target):
    cycle = await make_cycle(db, status=start)
    updated = await cycle_service.transition(db, cycle, target)
    assert updated.status is target


async def test_timestamps_are_stamped_on_the_right_steps(db):
    cycle = await make_cycle(db, status=CycleStatus.aggregated)

    approved = await cycle_service.transition(db, cycle, CycleStatus.approved)
    assert approved.approved_at is not None
    assert approved.ordered_at is None

    ordered = await cycle_service.transition(db, cycle, CycleStatus.ordered)
    assert ordered.ordered_at is not None

    received = await cycle_service.transition(db, cycle, CycleStatus.received)
    assert received.received_at is not None


async def test_stepping_back_clears_the_undone_timestamp(db):
    # aggregated -> approved (stamps approved_at) -> reject back to aggregated
    # should clear approved_at, so history never claims a false approval time.
    cycle = await make_cycle(db, status=CycleStatus.aggregated)
    await cycle_service.transition(db, cycle, CycleStatus.approved)
    assert cycle.approved_at is not None

    reverted = await cycle_service.transition(db, cycle, CycleStatus.aggregated)
    assert reverted.status is CycleStatus.aggregated
    assert reverted.approved_at is None


async def test_stepping_back_below_aggregated_clears_the_snapshot(db):
    # The frozen weekly_order_lines only reflect demand at aggregation time.
    # Reopening the cycle (aggregated -> locked) must discard them, or the
    # shopping list reports stale totals against a live per-customer breakdown.
    cycle = await make_cycle(db, status=CycleStatus.aggregated)
    product = await make_product(db)
    await _add_snapshot_line(db, cycle, product)
    assert await _snapshot_line_count(db, cycle.id) == 1

    await cycle_service.transition(db, cycle, CycleStatus.locked)
    assert await _snapshot_line_count(db, cycle.id) == 0


async def test_reject_to_aggregated_keeps_the_snapshot(db):
    # Rejecting approved -> aggregated stays at the aggregated level, so the
    # snapshot is still valid and must be kept.
    cycle = await make_cycle(db, status=CycleStatus.approved)
    product = await make_product(db)
    await _add_snapshot_line(db, cycle, product)

    await cycle_service.transition(db, cycle, CycleStatus.aggregated)
    assert await _snapshot_line_count(db, cycle.id) == 1


# --- Invalid transitions -----------------------------------------------------


@pytest.mark.parametrize(
    "start,target",
    [
        (CycleStatus.open, CycleStatus.ordered),      # skips locked+aggregated+approved
        (CycleStatus.open, CycleStatus.approved),     # skips ahead
        (CycleStatus.aggregated, CycleStatus.received),  # skips approved+ordered
        (CycleStatus.ordered, CycleStatus.approved),  # can't un-order
        (CycleStatus.received, CycleStatus.open),     # can't reopen a received week
    ],
)
async def test_invalid_transition_is_rejected(db, start, target):
    cycle = await make_cycle(db, status=start)
    with pytest.raises(HTTPException) as exc:
        await cycle_service.transition(db, cycle, target)
    assert exc.value.status_code == 422
    # State must be unchanged after a rejected move.
    assert cycle.status is start


async def test_closed_is_terminal(db):
    cycle = await make_cycle(db, status=CycleStatus.closed)
    for target in CycleStatus:
        if target is CycleStatus.closed:
            continue
        with pytest.raises(HTTPException):
            await cycle_service.transition(db, cycle, target)


async def test_closing_a_week_deletes_its_customer_orders_but_keeps_the_snapshot(db):
    # Closed weeks should not leave submitted orders sitting in the database
    # for the next dashboard/shopping-list read. The frozen snapshot stays so
    # the weeks archive can still show what was bought.
    product = await make_product(db)
    cycle = await make_cycle(db, status=CycleStatus.received)
    user = await make_user(db)
    await make_submitted_order(db, user=user, cycle=cycle, product=product, quantity=3)
    await _add_snapshot_line(db, cycle, product)

    await cycle_service.transition(db, cycle, CycleStatus.closed)

    remaining = await db.scalar(select(func.count()).select_from(Order).where(Order.weekly_cycle_id == cycle.id))
    assert remaining == 0
    assert await _snapshot_line_count(db, cycle.id) == 1


async def test_current_cycle_skips_a_closed_week(db):
    week_start = cycle_service.current_week_start()
    closed = await make_cycle(db, week_start=week_start, status=CycleStatus.closed)

    current = await cycle_service.get_or_create_current_cycle(db)

    assert current.id != closed.id
    assert current.week_start == week_start + timedelta(days=7)
    assert current.status is CycleStatus.open
