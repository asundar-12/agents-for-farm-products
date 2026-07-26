from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.customer import User, UserRole

settings = get_settings()

_bearer_scheme = HTTPBearer()


# --- Password hashing ---
# Using `bcrypt` directly rather than passlib: passlib's bcrypt backend has had
# repeated compatibility breaks with newer bcrypt releases, and all we need here
# is hash + verify, so the extra abstraction isn't worth the dependency risk.


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# --- Legacy JWT (auth_mode == "legacy") ---
# Self-signed HS256 tokens whose `sub` is the local users.id. Kept so local dev
# and any not-yet-migrated environment keep working without a Cognito pool.


class TokenData(BaseModel):
    # Always the LOCAL users.id, regardless of auth mode, so every router that
    # does uuid.UUID(current_user.user_id) keeps working unchanged.
    user_id: str
    role: str


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_legacy_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    user_id = payload.get("sub")
    role = payload.get("role")
    if user_id is None or role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return TokenData(user_id=user_id, role=role)


# --- Cognito JWT (auth_mode == "cognito") ---
# We do NOT sign tokens here anymore. Cognito issues RS256-signed ID tokens; we
# fetch the pool's public keys (JWKS) and verify signature + issuer + audience.
# The frontend must send the ID token (it carries email + name, which we need to
# link/create the local user), not the access token.


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    # The pool publishes its rotating public keys here. PyJWKClient fetches and
    # caches them, and picks the right key per token via the token's `kid`.
    issuer = _cognito_issuer()
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json")


def _cognito_issuer() -> str:
    return (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )


def _verify_cognito_token(token: str) -> dict:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,  # ID token `aud` == app client id
            issuer=_cognito_issuer(),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    # `token_use` distinguishes ID tokens ("id") from access tokens ("access").
    # We require an ID token because we need the email/name claims to link users.
    if claims.get("token_use") != "id":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an ID token",
        )
    return claims


async def _resolve_cognito_user(db: AsyncSession, claims: dict) -> User:
    """Map a verified Cognito ID token to the local users row.

    Order matters: match by the Cognito sub first (stable), then fall back to
    email for a migrated user we haven't linked yet (and backfill the sub), and
    finally create a fresh row for a brand-new Cognito signup.
    """
    sub = claims["sub"]
    email = claims.get("email")

    user = await db.scalar(select(User).where(User.cognito_sub == sub))
    if user is not None:
        return user

    if email is not None:
        user = await db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.cognito_sub = sub  # backfill the link on first Cognito login
            await db.commit()
            await db.refresh(user)
            return user

    # New Cognito user with no local row yet — create one. Default role is
    # customer; promoting to admin stays a deliberate DB change.
    user = User(
        email=email,
        cognito_sub=sub,
        full_name=claims.get("name") or email or "",
        role=UserRole.customer,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# --- Dependencies used by the routers ---


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenData:
    token = credentials.credentials

    if settings.auth_mode == "cognito":
        claims = _verify_cognito_token(token)
        user = await _resolve_cognito_user(db, claims)
        # Role is authoritative in our DB, not in the token — keeps admin
        # assignment a deliberate action rather than a Cognito group config.
        return TokenData(user_id=str(user.id), role=user.role.value)

    return _decode_legacy_token(token)


def require_role(*allowed_roles: str):
    def _check(current_user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _check
