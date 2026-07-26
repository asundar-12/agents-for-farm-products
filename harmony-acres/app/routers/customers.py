import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import TokenData, create_access_token, get_current_user

settings = get_settings()


def _require_legacy_auth() -> None:
    # In cognito mode there is no local password flow: sign-up and sign-in happen
    # against the User Pool, so these endpoints are turned off.
    if settings.auth_mode == "cognito":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password auth is disabled; sign in through Cognito",
        )
from app.schemas.customer import (
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
    _require_legacy_auth()
    user = await customer_service.register_user(db, data)
    return UserRead.model_validate(user)


@router.post("/auth/login", response_model=Token)
async def login(data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]) -> Token:
    _require_legacy_auth()
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
