import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenData, get_current_user
from app.schemas.order import OrderCreate, OrderRead
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    data: OrderCreate,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderRead:
    order = await order_service.create_order(db, uuid.UUID(current_user.user_id), data)
    return OrderRead.model_validate(order)


@router.get("", response_model=list[OrderRead])
async def list_orders(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OrderRead]:
    orders = await order_service.list_orders_for_user(db, uuid.UUID(current_user.user_id))
    return [OrderRead.model_validate(o) for o in orders]


@router.get("/upcoming", response_model=list[OrderRead])
async def list_upcoming_orders(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OrderRead]:
    orders = await order_service.get_upcoming_orders_for_user(db, uuid.UUID(current_user.user_id))
    return [OrderRead.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderRead:
    order = await order_service.get_order_by_id(db, order_id)
    order_service.assert_owned_by(order, uuid.UUID(current_user.user_id))
    return OrderRead.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: uuid.UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderRead:
    order = await order_service.cancel_order(db, uuid.UUID(current_user.user_id), order_id)
    return OrderRead.model_validate(order)
