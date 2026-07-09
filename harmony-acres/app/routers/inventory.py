from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_role
from app.schemas.inventory import InventorySummaryItem
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(require_role("admin"))])


@router.get("", response_model=list[InventorySummaryItem])
async def get_inventory(db: Annotated[AsyncSession, Depends(get_db)]) -> list[InventorySummaryItem]:
    return await inventory_service.get_inventory_summary(db)


@router.get("/low-stock", response_model=list[InventorySummaryItem])
async def get_low_stock(db: Annotated[AsyncSession, Depends(get_db)]) -> list[InventorySummaryItem]:
    return await inventory_service.get_low_stock_items(db)
