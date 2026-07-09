import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.subscription import Subscription, SubscriptionItem, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionItemCreate, SubscriptionUpdate
from app.services.scheduling import assert_wednesday

# Days between deliveries for each frequency, used by skip_next_delivery to
# advance the schedule. "monthly" is approximated as 4 weeks (28 days) rather
# than a calendar month so next_delivery_date always lands back on a Wednesday.
_FREQUENCY_INTERVAL_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 28,
}


async def get_subscription_by_id(db: AsyncSession, subscription_id: uuid.UUID) -> Subscription:
    # selectinload(items) avoids the "lazy load on a detached/async session" trap:
    # without it, touching subscription.items later would trigger an implicit
    # sync-style query that async SQLAlchemy can't do lazily and raises instead.
    # Chaining .selectinload(SubscriptionItem.product) the same way so
    # SubscriptionItem.product_name (used by SubscriptionItemRead) is safe to
    # access too.
    stmt = (
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(selectinload(Subscription.items).selectinload(SubscriptionItem.product))
    )
    subscription = await db.scalar(stmt)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


async def list_subscriptions_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Subscription]:
    stmt = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .options(selectinload(Subscription.items).selectinload(SubscriptionItem.product))
    )
    result = await db.scalars(stmt)
    return list(result.all())


def assert_owned_by(subscription: Subscription, user_id: uuid.UUID) -> None:
    if subscription.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your subscription")


async def get_next_delivery_for_user(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    stmt = (
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == SubscriptionStatus.active)
        .order_by(Subscription.next_delivery_date.asc())
        .limit(1)
    )
    return await db.scalar(stmt)


async def _assert_items_valid(db: AsyncSession, items: list[SubscriptionItemCreate]) -> None:
    for item in items:
        product = await db.get(Product, item.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item.product_id} not found"
            )
        if not product.is_available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{product.name}' is not currently available",
            )


async def create_subscription(db: AsyncSession, user_id: uuid.UUID, data: SubscriptionCreate) -> Subscription:
    assert_wednesday(data.next_delivery_date, "next_delivery_date")
    await _assert_items_valid(db, data.items)

    subscription = Subscription(
        user_id=user_id,
        pickup_location=data.pickup_location,
        frequency=data.frequency,
        next_delivery_date=data.next_delivery_date,
        status=SubscriptionStatus.active,
        items=[SubscriptionItem(product_id=item.product_id, quantity=item.quantity) for item in data.items],
    )
    db.add(subscription)
    await db.commit()
    return await get_subscription_by_id(db, subscription.id)


async def pause_subscription(
    db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID, resume_on: date | None
) -> Subscription:
    subscription = await get_subscription_by_id(db, subscription_id)
    assert_owned_by(subscription, user_id)

    if subscription.status != SubscriptionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot pause a subscription that is '{subscription.status.value}'",
        )
    if resume_on is not None and resume_on <= date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="resume_on must be in the future"
        )

    subscription.status = SubscriptionStatus.paused
    subscription.paused_until = resume_on
    await db.commit()
    return await get_subscription_by_id(db, subscription.id)


async def resume_subscription(db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID) -> Subscription:
    subscription = await get_subscription_by_id(db, subscription_id)
    assert_owned_by(subscription, user_id)

    if subscription.status != SubscriptionStatus.paused:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot resume a subscription that is '{subscription.status.value}'",
        )

    subscription.status = SubscriptionStatus.active
    subscription.paused_until = None
    await db.commit()
    return await get_subscription_by_id(db, subscription.id)


async def cancel_subscription(db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID) -> Subscription:
    subscription = await get_subscription_by_id(db, subscription_id)
    assert_owned_by(subscription, user_id)

    if subscription.status == SubscriptionStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Subscription is already cancelled")

    subscription.status = SubscriptionStatus.cancelled
    subscription.paused_until = None
    await db.commit()
    return await get_subscription_by_id(db, subscription.id)


async def update_subscription(
    db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID, data: SubscriptionUpdate
) -> Subscription:
    subscription = await get_subscription_by_id(db, subscription_id)
    assert_owned_by(subscription, user_id)

    if subscription.status == SubscriptionStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot modify a cancelled subscription"
        )

    if data.frequency is not None:
        subscription.frequency = data.frequency
    if data.items is not None:
        await _assert_items_valid(db, data.items)
        # Reassigning the relationship (rather than mutating in place) relies on
        # cascade="all, delete-orphan" on Subscription.items to delete the old
        # SubscriptionItem rows and insert the new ones in the same flush.
        subscription.items = [
            SubscriptionItem(product_id=item.product_id, quantity=item.quantity) for item in data.items
        ]

    await db.commit()
    return await get_subscription_by_id(db, subscription.id)


async def skip_next_delivery(db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID) -> Subscription:
    subscription = await get_subscription_by_id(db, subscription_id)
    assert_owned_by(subscription, user_id)

    if subscription.status != SubscriptionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot skip a delivery for a subscription that is '{subscription.status.value}'",
        )

    interval_days = _FREQUENCY_INTERVAL_DAYS[subscription.frequency.value]
    subscription.next_delivery_date = subscription.next_delivery_date + timedelta(days=interval_days)
    await db.commit()
    return await get_subscription_by_id(db, subscription.id)
