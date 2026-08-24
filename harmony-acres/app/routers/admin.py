"""Farm-side endpoints.

Every route here is behind `require_role("admin")` at the router level rather
than per-endpoint — a new admin route is protected by default, and forgetting
the dependency can't silently expose farm-wide data the way a missed decorator
would. This is also where `require_role` finally gets used: before this, the
only thing keeping operational data out of customer hands was a line in the
agent's prompt, which was never enforcement.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_role
from app.models.customer import User, UserRole
from app.models.weekly import CycleStatus
from app.schemas.weekly import (
    AdminNotesUpdate,
    CustomerRead,
    CycleSummary,
    MarkReceivedRequest,
    NonSubmitter,
    SetLineQuantity,
    ShoppingList,
    WeeklyCycleRead,
)
from app.services import aggregation_service, cycle_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)


# --- Dashboard ---------------------------------------------------------------


@router.get("/dashboard", response_model=CycleSummary)
async def get_dashboard(db: Annotated[AsyncSession, Depends(get_db)]) -> CycleSummary:
    """Headline numbers for the week currently in flight.

    Locks any cycle whose deadline has passed first, so the dashboard reflects
    reality without depending on a scheduler that doesn't exist yet.
    """
    await cycle_service.lock_expired_cycles(db)
    cycle = await cycle_service.get_or_create_current_cycle(db)
    return await aggregation_service.get_cycle_summary(db, cycle.id)


# --- Cycles ------------------------------------------------------------------


@router.get("/cycles", response_model=list[WeeklyCycleRead])
async def list_cycles(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 26,
) -> list[WeeklyCycleRead]:
    """Past and current weeks, newest first. Backs /admin/weeks."""
    await cycle_service.lock_expired_cycles(db)
    cycles = await cycle_service.list_cycles(db, limit=limit)
    return [WeeklyCycleRead.model_validate(c) for c in cycles]


@router.get("/cycles/current", response_model=WeeklyCycleRead)
async def get_current_cycle(db: Annotated[AsyncSession, Depends(get_db)]) -> WeeklyCycleRead:
    await cycle_service.lock_expired_cycles(db)
    cycle = await cycle_service.get_or_create_current_cycle(db)
    return WeeklyCycleRead.model_validate(cycle)


@router.get("/cycles/{cycle_id}", response_model=WeeklyCycleRead)
async def get_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    return WeeklyCycleRead.model_validate(cycle)


@router.get("/cycles/{cycle_id}/shopping-list", response_model=ShoppingList)
async def get_shopping_list(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ShoppingList:
    """The buy list, with per-customer expansion and week-over-week movement."""
    return await aggregation_service.get_shopping_list(db, cycle_id)


@router.patch("/cycles/{cycle_id}/lines/{product_id}", response_model=ShoppingList)
async def adjust_line(
    cycle_id: uuid.UUID,
    product_id: uuid.UUID,
    data: SetLineQuantity,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShoppingList:
    """Override the quantity to actually order for one product.

    For post-deadline changes: a customer phones to drop or add something after
    the window closed. Their submitted order stays as the record of what they
    asked for; only the consolidated buy quantity moves. Send quantity=null to
    clear an override and revert to the aggregated total.
    """
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    await aggregation_service.set_line_quantity(db, cycle, product_id, data.quantity)
    return await aggregation_service.get_shopping_list(db, cycle_id)


@router.get("/cycles/{cycle_id}/non-submitters", response_model=list[NonSubmitter])
async def get_non_submitters(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[NonSubmitter]:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    return await aggregation_service.list_non_submitters(db, cycle)


@router.patch("/cycles/{cycle_id}/notes", response_model=WeeklyCycleRead)
async def update_notes(
    cycle_id: uuid.UUID,
    data: AdminNotesUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyCycleRead:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle.admin_notes = data.admin_notes
    await db.commit()
    return WeeklyCycleRead.model_validate(cycle)


# --- Lifecycle ---------------------------------------------------------------
# Each step is its own endpoint rather than one "set status" route: the legal
# moves are fixed, and naming them means the client can't invent a transition.


@router.post("/cycles/{cycle_id}/lock", response_model=WeeklyCycleRead)
async def lock_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    """Close ordering early, before the deadline."""
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.locked)
    return WeeklyCycleRead.model_validate(cycle)


@router.post("/cycles/{cycle_id}/reopen", response_model=WeeklyCycleRead)
async def reopen_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    """Reopen a locked week — only useful while its deadline is still ahead."""
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.open)
    return WeeklyCycleRead.model_validate(cycle)


@router.post("/cycles/{cycle_id}/aggregate", response_model=ShoppingList)
async def aggregate_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ShoppingList:
    """Freeze the week's demand into a shopping list."""
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    await aggregation_service.aggregate_cycle(db, cycle)
    return await aggregation_service.get_shopping_list(db, cycle_id)


@router.post("/cycles/{cycle_id}/approve", response_model=WeeklyCycleRead)
async def approve_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.approved)
    return WeeklyCycleRead.model_validate(cycle)


@router.post("/cycles/{cycle_id}/reject", response_model=WeeklyCycleRead)
async def reject_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    """Send an approved week back for another look.

    Only possible before it's marked ordered — once the real order is placed
    with the farm, un-approving it would be a fiction.
    """
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.aggregated)
    return WeeklyCycleRead.model_validate(cycle)


@router.post("/cycles/{cycle_id}/mark-ordered", response_model=WeeklyCycleRead)
async def mark_ordered(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    """Record that the order was placed with the farm by hand."""
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.ordered)
    return WeeklyCycleRead.model_validate(cycle)


@router.post("/cycles/{cycle_id}/mark-received", response_model=ShoppingList)
async def mark_received(
    cycle_id: uuid.UUID,
    data: MarkReceivedRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShoppingList:
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    received = {line.product_id: line.received_quantity for line in data.lines} if data.lines else None
    await aggregation_service.record_received(db, cycle, received)
    await cycle_service.transition(db, cycle, CycleStatus.received)
    return await aggregation_service.get_shopping_list(db, cycle_id)


@router.post("/cycles/{cycle_id}/close", response_model=WeeklyCycleRead)
async def close_cycle(
    cycle_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> WeeklyCycleRead:
    """Archive the week. Terminal — nothing moves after this.

    Also deletes this week's customer orders (not subscriptions) so they
    don't linger as live demand on the next week's dashboard.
    """
    cycle = await cycle_service.get_cycle_by_id(db, cycle_id)
    cycle = await cycle_service.transition(db, cycle, CycleStatus.closed)
    return WeeklyCycleRead.model_validate(cycle)


# --- Customers ---------------------------------------------------------------


@router.get("/customers", response_model=list[CustomerRead])
async def list_customers(db: Annotated[AsyncSession, Depends(get_db)]) -> list[CustomerRead]:
    stmt = select(User).where(User.role == UserRole.customer).order_by(User.full_name)
    customers = (await db.scalars(stmt)).all()
    return [CustomerRead.model_validate(c) for c in customers]
