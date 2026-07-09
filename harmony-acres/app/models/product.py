import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductCategory(str, enum.Enum):
    dairy = "dairy"
    eggs = "eggs"
    pantry = "pantry"
    other = "other"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[ProductCategory] = mapped_column(Enum(ProductCategory, name="product_category"), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # Numeric (not Float) for money — avoids binary floating-point rounding errors.
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
