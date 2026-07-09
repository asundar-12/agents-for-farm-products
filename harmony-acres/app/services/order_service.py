import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Inventory
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.schemas.order import OrderCreate
from app.services.scheduling import assert_wednesday

# Orders in these statuses haven't entered fulfillment yet, so they're still
# cancellable. "ready" means staff have already pulled/packed the items.
_CANCELLABLE_STATUSES = (OrderStatus.pending, OrderStatus.confirmed)


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order:
    stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
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
        .options(selectinload(Order.items))
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
        .options(selectinload(Order.items))
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def create_order(db: AsyncSession, user_id: uuid.UUID, data: OrderCreate) -> Order:
    assert_wednesday(data.order_date, "order_date")

    total_amount = Decimal("0")
    order_items: list[OrderItem] = []

    for item in data.items:
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

        inventory = await db.scalar(
            select(Inventory).where(Inventory.product_id == product.id).with_for_update()
        )
        quantity_on_hand = inventory.quantity_on_hand if inventory is not None else 0
        if quantity_on_hand < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Not enough stock for '{product.name}': requested {item.quantity}, "
                    f"{quantity_on_hand} on hand"
                ),
            )

        if inventory is not None:
            inventory.quantity_on_hand -= item.quantity

        unit_price = Decimal(str(product.unit_price))
        total_amount += unit_price * item.quantity
        order_items.append(OrderItem(product_id=product.id, quantity=item.quantity, unit_price=unit_price))

    order = Order(
        user_id=user_id,
        pickup_location=data.pickup_location,
        order_date=data.order_date,
        status=OrderStatus.pending,
        total_amount=total_amount,
        items=order_items,
    )
    db.add(order)
    await db.commit()
    return await get_order_by_id(db, order.id)


async def cancel_order(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await get_order_by_id(db, order_id)
    assert_owned_by(order, user_id)

    if order.status not in _CANCELLABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Order cannot be cancelled once it is '{order.status.value}'",
        )

    for item in order.items:
        inventory = await db.scalar(
            select(Inventory).where(Inventory.product_id == item.product_id).with_for_update()
        )
        if inventory is not None:
            inventory.quantity_on_hand += item.quantity

    order.status = OrderStatus.cancelled
    order.refund_amount = order.total_amount
    await db.commit()
    return await get_order_by_id(db, order.id)
