"""Weekly aggregation (business rule 3): the consolidated buy list.

Covers the auto-computed totals from many customer orders + subscriptions, the
per-customer breakdown, subscription due-dates, week-over-week movement/spikes,
and admin overrides of a line.

NOTE (flagged to the team): rule 3 also asks that admin edits to the aggregate
be *logged*. They are not — set_line_quantity overwrites adjusted_quantity with
no record of who/when/previous value. The final test documents that gap as an
expected failure (xfail) rather than pretending it passes.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.subscription import Subscription, SubscriptionFrequency, SubscriptionStatus
from app.models.weekly import CycleStatus, WeeklyCycle
from app.services import aggregation_service
from tests.factories import (
    make_cycle,
    make_line,
    make_product,
    make_submitted_order,
    make_subscription,
    make_user,
)


# --- Core math ---------------------------------------------------------------


async def test_totals_sum_orders_and_subscriptions(db):
    cycle = await make_cycle(db)
    product = await make_product(db, price="6.50")

    a = await make_user(db, email="a@test.com", full_name="Ann")
    b = await make_user(db, email="b@test.com", full_name="Ben")
    c = await make_user(db, email="c@test.com", full_name="Cara")

    await make_submitted_order(db, user=a, cycle=cycle, product=product, quantity=2)
    await make_submitted_order(db, user=b, cycle=cycle, product=product, quantity=3)
    # A subscription due exactly on the cycle's delivery date (weekly => due).
    await make_subscription(
        db, user=c, product=product, quantity=1, next_delivery_date=cycle.delivery_date
    )

    await aggregation_service.aggregate_cycle(db, cycle)
    sl = await aggregation_service.get_shopping_list(db, cycle.id)

    assert len(sl.lines) == 1
    line = sl.lines[0]
    assert line.order_quantity == 5  # 2 + 3
    assert line.subscription_quantity == 1
    assert line.total_quantity == 6
    assert line.effective_quantity == 6
    assert line.line_total == Decimal("39.00")  # 6 * 6.50
    assert sl.customer_count == 3
    assert sl.order_count == 2
    assert sl.subscription_count == 1


async def test_customer_breakdown_lists_each_participant(db):
    cycle = await make_cycle(db)
    product = await make_product(db)
    a = await make_user(db, email="a@test.com", full_name="Ann")
    b = await make_user(db, email="b@test.com", full_name="Ben")
    await make_submitted_order(db, user=a, cycle=cycle, product=product, quantity=4)
    await make_submitted_order(db, user=b, cycle=cycle, product=product, quantity=1)

    sl = await aggregation_service.get_shopping_list(db, cycle.id)
    names = {c.full_name for c in sl.lines[0].customers}
    assert names == {"Ann", "Ben"}
    # Sorted by quantity desc — the biggest share first.
    assert sl.lines[0].customers[0].full_name == "Ann"


# --- Subscription due logic (pure function, no DB) ---------------------------


def _sub(status, next_date, freq=SubscriptionFrequency.weekly):
    return Subscription(
        status=status, next_delivery_date=next_date, frequency=freq, user_id=None
    )


def test_subscription_due_matches_frequency_interval():
    delivery = date(2026, 3, 11)  # a Wednesday
    cycle = WeeklyCycle(week_start=date(2026, 3, 9), delivery_date=delivery, submission_deadline=None)

    # Weekly, last delivered exactly 7 days ago -> due.
    assert aggregation_service.subscription_due_in_cycle(
        _sub(SubscriptionStatus.active, delivery - timedelta(days=7)), cycle
    ) is True
    # Biweekly, 7 days out -> NOT a multiple of 14 -> not due.
    assert aggregation_service.subscription_due_in_cycle(
        _sub(SubscriptionStatus.active, delivery - timedelta(days=7), SubscriptionFrequency.biweekly),
        cycle,
    ) is False
    # Starts in the future -> not due.
    assert aggregation_service.subscription_due_in_cycle(
        _sub(SubscriptionStatus.active, delivery + timedelta(days=7)), cycle
    ) is False
    # Paused -> never due, even if the date lines up.
    assert aggregation_service.subscription_due_in_cycle(
        _sub(SubscriptionStatus.paused, delivery), cycle
    ) is False


# --- Week-over-week movement & spikes ----------------------------------------


async def test_delta_and_spike_flagged_on_large_jump(db):
    product = await make_product(db, price="2.00")
    # Previous cycle: an aggregated line with total 4.
    prev = await make_cycle(
        db, week_start=date.today() - timedelta(days=14), status=CycleStatus.closed
    )
    await make_line(db, cycle=prev, product=product, order_quantity=4)

    # Current cycle: demand of 10 for the same product.
    cur = await make_cycle(db, week_start=date.today())
    user = await make_user(db)
    await make_submitted_order(db, user=user, cycle=cur, product=product, quantity=10)

    sl = await aggregation_service.get_shopping_list(db, cur.id)
    line = next(l for l in sl.lines if l.product_id == product.id)
    assert line.previous_total == 4
    assert line.delta == 6
    assert line.is_spike is True  # +150% and +6 units clears both thresholds


async def test_small_movement_is_not_a_spike(db):
    product = await make_product(db, price="2.00")
    prev = await make_cycle(
        db, week_start=date.today() - timedelta(days=14), status=CycleStatus.closed
    )
    await make_line(db, cycle=prev, product=product, order_quantity=10)

    cur = await make_cycle(db, week_start=date.today())
    user = await make_user(db)
    await make_submitted_order(db, user=user, cycle=cur, product=product, quantity=11)

    sl = await aggregation_service.get_shopping_list(db, cur.id)
    line = next(l for l in sl.lines if l.product_id == product.id)
    assert line.delta == 1
    assert line.is_spike is False  # only +1 unit, below the absolute floor


# --- Admin override of a line ------------------------------------------------


async def test_override_changes_effective_quantity_not_total(db):
    cycle = await make_cycle(db, status=CycleStatus.aggregated)
    product = await make_product(db, price="5.00")
    await make_line(db, cycle=cycle, product=product, order_quantity=6)

    await aggregation_service.set_line_quantity(db, cycle, product.id, 4)

    sl = await aggregation_service.get_shopping_list(db, cycle.id)
    line = sl.lines[0]
    assert line.total_quantity == 6          # what customers actually asked for
    assert line.adjusted_quantity == 4       # admin override
    assert line.effective_quantity == 4      # what the farm is asked to buy
    assert line.line_total == Decimal("20.00")  # cost follows effective, 4 * 5.00


async def test_override_rejected_before_aggregation(db):
    cycle = await make_cycle(db, status=CycleStatus.open)
    product = await make_product(db)
    with pytest.raises(HTTPException) as exc:
        await aggregation_service.set_line_quantity(db, cycle, product.id, 3)
    assert exc.value.status_code == 422


async def test_override_rejected_after_ordered(db):
    cycle = await make_cycle(db, status=CycleStatus.ordered)
    product = await make_product(db)
    await make_line(db, cycle=cycle, product=product, order_quantity=6)
    with pytest.raises(HTTPException) as exc:
        await aggregation_service.set_line_quantity(db, cycle, product.id, 3)
    assert exc.value.status_code == 422


@pytest.mark.xfail(
    reason="Rule 3 asks that aggregate edits be logged, but set_line_quantity "
    "overwrites adjusted_quantity with no audit trail (who/when/previous value). "
    "Flagged as a gap; this stays xfail until an audit log is added.",
    strict=True,
)
async def test_admin_override_is_logged(db):
    cycle = await make_cycle(db, status=CycleStatus.aggregated)
    product = await make_product(db)
    line = await make_line(db, cycle=cycle, product=product, order_quantity=10)

    await aggregation_service.set_line_quantity(db, cycle, product.id, 8)
    await aggregation_service.set_line_quantity(db, cycle, product.id, 6)

    # There is no audit-log model or history field anywhere, so the earlier
    # value (8) and who set it are unrecoverable. Nothing to assert against ->
    # this is expected to fail until logging exists.
    assert hasattr(line, "adjustment_history")
