import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenData, get_current_user
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionPause,
    SubscriptionRead,
    SubscriptionUpdate,
)
from app.services import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionRead, status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.create_subscription(db, uuid.UUID(current_user.user_id), data)
    return SubscriptionRead.model_validate(subscription)


@router.get("/{subscription_id}", response_model=SubscriptionRead)
async def get_subscription(
    subscription_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.get_subscription_by_id(db, subscription_id)
    subscription_service.assert_owned_by(subscription, uuid.UUID(current_user.user_id))
    return SubscriptionRead.model_validate(subscription)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
async def update_subscription(
    subscription_id: uuid.UUID,
    data: SubscriptionUpdate,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.update_subscription(
        db, uuid.UUID(current_user.user_id), subscription_id, data
    )
    return SubscriptionRead.model_validate(subscription)


@router.post("/{subscription_id}/pause", response_model=SubscriptionRead)
async def pause_subscription(
    subscription_id: uuid.UUID,
    data: SubscriptionPause,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.pause_subscription(
        db, uuid.UUID(current_user.user_id), subscription_id, data.resume_on
    )
    return SubscriptionRead.model_validate(subscription)


@router.post("/{subscription_id}/resume", response_model=SubscriptionRead)
async def resume_subscription(
    subscription_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.resume_subscription(
        db, uuid.UUID(current_user.user_id), subscription_id
    )
    return SubscriptionRead.model_validate(subscription)


@router.post("/{subscription_id}/skip-next", response_model=SubscriptionRead)
async def skip_next_delivery(
    subscription_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.skip_next_delivery(
        db, uuid.UUID(current_user.user_id), subscription_id
    )
    return SubscriptionRead.model_validate(subscription)


@router.post("/{subscription_id}/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    subscription = await subscription_service.cancel_subscription(
        db, uuid.UUID(current_user.user_id), subscription_id
    )
    return SubscriptionRead.model_validate(subscription)
