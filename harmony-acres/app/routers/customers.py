import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import TokenData, create_access_token, get_current_user
from app.schemas.customer import (
    AddressCreate,
    AddressRead,
    Token,
    UserLogin,
    UserRead,
    UserRegister,
    UserUpdate,
)
from app.services import customer_service

router = APIRouter(tags=["customers"])


@router.post("/auth/register", response_model=UserRead, status_code=201)
async def register(data: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    user = await customer_service.register_user(db, data)
    return UserRead.model_validate(user)


@router.post("/auth/login", response_model=Token)
async def login(data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]) -> Token:
    user = await customer_service.authenticate_user(db, data.email, data.password)
    access_token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=access_token)


@router.get("/customers/me", response_model=UserRead)
async def get_me(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    user = await customer_service.get_user_by_id(db, uuid.UUID(current_user.user_id))
    return UserRead.model_validate(user)


@router.patch("/customers/me", response_model=UserRead)
async def update_me(
    data: UserUpdate,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    user = await customer_service.update_user(db, uuid.UUID(current_user.user_id), data.full_name)
    return UserRead.model_validate(user)


@router.get("/customers/me/addresses", response_model=list[AddressRead])
async def list_my_addresses(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AddressRead]:
    addresses = await customer_service.list_addresses(db, uuid.UUID(current_user.user_id))
    return [AddressRead.model_validate(a) for a in addresses]


@router.post("/customers/me/addresses", response_model=AddressRead, status_code=201)
async def create_my_address(
    data: AddressCreate,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AddressRead:
    address = await customer_service.create_address(db, uuid.UUID(current_user.user_id), data)
    return AddressRead.model_validate(address)
