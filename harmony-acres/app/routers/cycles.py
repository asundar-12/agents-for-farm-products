from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenData, get_current_user
from app.schemas.weekly import WeeklyCycleSummary
from app.services import cycle_service

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.get("/current", response_model=WeeklyCycleSummary)
async def get_current_cycle(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyCycleSummary:
    """This week's ordering window.

    Every customer screen reads `is_open` from here rather than comparing the
    deadline to its own clock, so the lock lands on all of them at the same
    moment and a client with a skewed clock can't keep editing.
    """
    cycle = await cycle_service.get_or_create_current_cycle(db)
    return WeeklyCycleSummary(
        id=cycle.id,
        week_start=cycle.week_start,
        submission_deadline=cycle.submission_deadline,
        delivery_date=cycle.delivery_date,
        status=cycle.status,
        is_open=cycle_service.is_open(cycle),
    )
