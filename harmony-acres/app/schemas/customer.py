import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.customer import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    # from_attributes=True lets this be built directly from an ORM `User` instance
    # (model_validate(user_obj)) instead of requiring a dict — Pydantic reads
    # attributes off the object rather than keys off a mapping.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None


class AddressCreate(BaseModel):
    label: str
    street: str
    city: str
    state: str
    zip: str
    is_default: bool = False


class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    street: str
    city: str
    state: str
    zip: str
    is_default: bool
    created_at: datetime
