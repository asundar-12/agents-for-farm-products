"""Small helpers to seed rows and build auth headers.

Plain async functions rather than a factory library — the schema is small and
explicit calls keep each test readable about exactly what data it depends on.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.customer import User, UserRole
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductCategory
from app.models.subscription import (
    Subscription,
    SubscriptionFrequency,
    SubscriptionItem,
    SubscriptionStatus,
)
from app.models.weekly import CycleStatus, WeeklyCycle, WeeklyOrderLine

DEFAULT_PASSWORD = "password123"


async def make_user(
    db: AsyncSession,
    *,
    email: str | None = None,
    role: UserRole = UserRole.customer,
    full_name: str = "Test Customer",
    password: str = DEFAULT_PASSWORD,
) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_product(
    db: AsyncSession,
    *,
    name: str = "Whole Milk (1 Gal)",
    price: str = "6.50",
    category: ProductCategory = ProductCategory.dairy,
    unit: str = "gallon",
    is_available: bool = True,
) -> Product:
    product = Product(
        name=name,
        category=category,
        unit_price=Decimal(price),
        unit=unit,
        is_available=is_available,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def make_cycle(
    db: AsyncSession,
    *,
    week_start: date | None = None,
    status: CycleStatus = CycleStatus.open,
    deadline: datetime | None = None,
    delivery_date: date | None = None,
) -> WeeklyCycle:
    # Default to a week whose deadline is comfortably in the future, so is_open
    # is true unless a test deliberately sets a past deadline.
    ws = week_start or (datetime.now(timezone.utc).date() - timedelta(days=datetime.now(timezone.utc).weekday()))
    cycle = WeeklyCycle(
        week_start=ws,
        submission_deadline=deadline or (datetime.now(timezone.utc) + timedelta(days=3)),
        delivery_date=delivery_date or (ws + timedelta(days=2)),
        status=status,
    )
    db.add(cycle)
    await db.commit()
    await db.refresh(cycle)
    return cycle


async def make_submitted_order(
    db: AsyncSession,
    *,
    user: User,
    cycle: WeeklyCycle,
    product: Product,
    quantity: int,
) -> Order:
    order = Order(
        user_id=user.id,
        weekly_cycle_id=cycle.id,
        pickup_location="Farm stand",
        order_date=cycle.delivery_date,
        status=OrderStatus.submitted,
        submitted_at=datetime.now(timezone.utc),
        total_amount=Decimal(str(product.unit_price)) * quantity,
    )
    order.items.append(
        OrderItem(product_id=product.id, quantity=quantity, unit_price=Decimal(str(product.unit_price)))
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def make_subscription(
    db: AsyncSession,
    *,
    user: User,
    product: Product,
    quantity: int,
    next_delivery_date: date,
    frequency: SubscriptionFrequency = SubscriptionFrequency.weekly,
    status: SubscriptionStatus = SubscriptionStatus.active,
) -> Subscription:
    sub = Subscription(
        user_id=user.id,
        pickup_location="Farm stand",
        frequency=frequency,
        next_delivery_date=next_delivery_date,
        status=status,
    )
    sub.items.append(SubscriptionItem(product_id=product.id, quantity=quantity))
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def make_line(
    db: AsyncSession,
    *,
    cycle: WeeklyCycle,
    product: Product,
    order_quantity: int = 0,
    subscription_quantity: int = 0,
    adjusted_quantity: int | None = None,
) -> WeeklyOrderLine:
    line = WeeklyOrderLine(
        cycle_id=cycle.id,
        product_id=product.id,
        order_quantity=order_quantity,
        subscription_quantity=subscription_quantity,
        total_quantity=order_quantity + subscription_quantity,
        adjusted_quantity=adjusted_quantity,
        unit_price=Decimal(str(product.unit_price)),
    )
    db.add(line)
    await db.commit()
    await db.refresh(line)
    return line


def auth_headers(user: User) -> dict[str, str]:
    """A valid bearer token for this user's id and role."""
    token = create_access_token(str(user.id), user.role.value)
    return {"Authorization": f"Bearer {token}"}
