"""Weekly cycle lifecycle.

A cycle is the unit everything else hangs off: customers edit a draft inside
the *current* cycle, and the admin approves/orders/receives that same cycle
after it locks. Cycles are created lazily on first access rather than by a cron
job, so there's nothing to fall behind if the app sits idle for a week.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.weekly import CycleStatus, WeeklyCycle, WeeklyOrderLine

# A cycle stops accepting customer edits in any of these states.
_EDITABLE_STATUSES = (CycleStatus.open,)


def week_start_for(day: date) -> date:
    """The Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def _dates_for_week(week_start: date) -> tuple[date, datetime]:
    settings = get_settings()
    delivery_date = week_start + timedelta(days=settings.delivery_weekday)
    deadline = datetime(
        week_start.year,
        week_start.month,
        week_start.day,
        tzinfo=timezone.utc,
    ) + timedelta(days=settings.deadline_weekday, hours=settings.deadline_hour_utc)
    return delivery_date, deadline


def current_week_start(now: datetime | None = None) -> date:
    """Which week customers are ordering into right now.

    Once this week's deadline passes, "current" rolls forward to next week —
    otherwise a customer arriving Wednesday morning would be handed a locked
    cycle and no way to order anything at all.

    Takes `now` as an argument so the roll-forward rule is testable without a
    clock or a database.
    """
    now = now or datetime.now(timezone.utc)
    week_start = week_start_for(now.date())
    _, deadline = _dates_for_week(week_start)
    return week_start + timedelta(days=7) if now >= deadline else week_start


async def get_or_create_current_cycle(db: AsyncSession) -> WeeklyCycle:
    return await get_or_create_cycle_for_week(db, current_week_start())


async def get_or_create_cycle_for_week(db: AsyncSession, week_start: date) -> WeeklyCycle:
    cycle = await db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == week_start))
    if cycle is not None:
        return cycle

    delivery_date, deadline = _dates_for_week(week_start)
    cycle = WeeklyCycle(
        week_start=week_start,
        submission_deadline=deadline,
        delivery_date=delivery_date,
        status=CycleStatus.open,
    )
    db.add(cycle)
    try:
        await db.commit()
    except IntegrityError:
        # Two requests raced to create the same week. week_start is unique, so
        # exactly one won — roll back and read the winner's row.
        await db.rollback()
        cycle = await db.scalar(select(WeeklyCycle).where(WeeklyCycle.week_start == week_start))
        if cycle is None:  # pragma: no cover - only if the unique index vanished
            raise
    return cycle


async def get_cycle_by_id(db: AsyncSession, cycle_id: uuid.UUID) -> WeeklyCycle:
    cycle = await db.get(WeeklyCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly cycle not found")
    return cycle


async def get_cycle_with_lines(db: AsyncSession, cycle_id: uuid.UUID) -> WeeklyCycle:
    stmt = (
        select(WeeklyCycle)
        .where(WeeklyCycle.id == cycle_id)
        .options(selectinload(WeeklyCycle.lines).selectinload(WeeklyOrderLine.product))
    )
    cycle = await db.scalar(stmt)
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly cycle not found")
    return cycle


async def list_cycles(db: AsyncSession, limit: int = 26) -> list[WeeklyCycle]:
    stmt = select(WeeklyCycle).order_by(WeeklyCycle.week_start.desc()).limit(limit)
    result = await db.scalars(stmt)
    return list(result.all())


def is_open(cycle: WeeklyCycle) -> bool:
    """Whether customers can still edit drafts in this cycle.

    Both halves matter: an admin can lock a cycle early by advancing its status,
    and a cycle nobody has locked yet still goes read-only the moment its
    deadline passes.
    """
    return cycle.status in _EDITABLE_STATUSES and datetime.now(timezone.utc) < cycle.submission_deadline


def assert_open(cycle: WeeklyCycle) -> None:
    if not is_open(cycle):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This week's ordering window has closed. Your next chance to order "
                "opens with the following week's cycle."
            ),
        )


# The admin's path through a week, and the only moves allowed off each state.
# Encoded as data rather than as branches in each endpoint so an illegal
# transition is impossible to reach by calling endpoints out of order —
# double-submitting "mark ordered" fails the second time instead of silently
# re-stamping ordered_at.
_ALLOWED_TRANSITIONS: dict[CycleStatus, tuple[CycleStatus, ...]] = {
    CycleStatus.open: (CycleStatus.locked,),
    CycleStatus.locked: (CycleStatus.aggregated, CycleStatus.open),
    CycleStatus.aggregated: (CycleStatus.approved, CycleStatus.locked),
    # Rejecting an approved cycle drops it back for another look, which is only
    # honest before the order has actually been placed with the farm.
    CycleStatus.approved: (CycleStatus.ordered, CycleStatus.aggregated),
    CycleStatus.ordered: (CycleStatus.received,),
    CycleStatus.received: (CycleStatus.closed,),
    CycleStatus.closed: (),
}

# Timestamps stamped as a cycle reaches each state.
_STATUS_TIMESTAMP = {
    CycleStatus.approved: "approved_at",
    CycleStatus.ordered: "ordered_at",
    CycleStatus.received: "received_at",
}


async def transition(db: AsyncSession, cycle: WeeklyCycle, target: CycleStatus) -> WeeklyCycle:
    if target not in _ALLOWED_TRANSITIONS[cycle.status]:
        allowed = ", ".join(s.value for s in _ALLOWED_TRANSITIONS[cycle.status]) or "nothing"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"A cycle that is '{cycle.status.value}' cannot move to "
                f"'{target.value}' (allowed: {allowed})"
            ),
        )

    cycle.status = target
    if target in _STATUS_TIMESTAMP:
        setattr(cycle, _STATUS_TIMESTAMP[target], datetime.now(timezone.utc))
    # Stepping backwards clears the timestamp of the state being undone, so
    # "approved_at" never claims a cycle was approved at a time it wasn't.
    for state, field in _STATUS_TIMESTAMP.items():
        if _rank(state) > _rank(target):
            setattr(cycle, field, None)

    await db.commit()
    return cycle


_STATUS_ORDER = [
    CycleStatus.open,
    CycleStatus.locked,
    CycleStatus.aggregated,
    CycleStatus.approved,
    CycleStatus.ordered,
    CycleStatus.received,
    CycleStatus.closed,
]


def _rank(state: CycleStatus) -> int:
    return _STATUS_ORDER.index(state)


async def lock_expired_cycles(db: AsyncSession) -> int:
    """Move any open-but-expired cycle to `locked`.

    Called at the top of admin reads so the dashboard reflects reality without
    depending on a scheduler existing.
    """
    now = datetime.now(timezone.utc)
    stmt = select(WeeklyCycle).where(
        WeeklyCycle.status == CycleStatus.open, WeeklyCycle.submission_deadline <= now
    )
    expired = list((await db.scalars(stmt)).all())
    for cycle in expired:
        cycle.status = CycleStatus.locked
    if expired:
        await db.commit()
    return len(expired)
