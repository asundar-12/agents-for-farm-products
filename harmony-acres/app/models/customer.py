import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    # Mapped[uuid.UUID] + mapped_column is SQLAlchemy 2.0's typed style: the Python
    # type on the left (Mapped[...]) is what your editor/mypy sees, the
    # mapped_column(...) on the right is the actual DB column definition.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # Nullable now: users created via Cognito have no password stored here —
    # Cognito owns the credential. Only legacy/self-registered users have a hash.
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    # Cognito's stable user id (the token `sub`). Populated on first Cognito
    # login (backfilled from email for migrated users). Lets us resolve a token
    # to the local row even if the email later changes.
    cognito_sub: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.customer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
