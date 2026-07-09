import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.customer import Address, User
from app.schemas.customer import AddressCreate, UserRegister


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, full_name: str | None) -> User:
    user = await get_user_by_id(db, user_id)
    if full_name is not None:
        user.full_name = full_name
    await db.commit()
    await db.refresh(user)
    return user


async def list_addresses(db: AsyncSession, user_id: uuid.UUID) -> list[Address]:
    result = await db.scalars(select(Address).where(Address.user_id == user_id))
    return list(result.all())


async def create_address(db: AsyncSession, user_id: uuid.UUID, data: AddressCreate) -> Address:
    address = Address(user_id=user_id, **data.model_dump())
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address
