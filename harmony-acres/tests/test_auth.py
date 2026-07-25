"""Auth: password hashing and JWT validation (business rule 6).

The protected endpoint used throughout is GET /customers/me — it does nothing
but echo the caller, so a 200 means "the token was accepted" and a 401/403
means "rejected", with no other logic in the way.
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from tests.factories import auth_headers, make_user

settings = get_settings()


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# --- Password hashing --------------------------------------------------------


def test_password_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"  # never store the raw password
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


# --- Happy path --------------------------------------------------------------


async def test_valid_token_is_accepted(client, db):
    user = await make_user(db)
    res = await client.get("/customers/me", headers=auth_headers(user))
    assert res.status_code == 200
    assert res.json()["id"] == str(user.id)


# --- Negative cases ----------------------------------------------------------


async def test_missing_token_is_rejected(client):
    res = await client.get("/customers/me")  # no Authorization header
    # HTTPBearer rejects a missing credential before our code runs.
    assert res.status_code in (401, 403)


async def test_malformed_token_is_rejected(client):
    res = await client.get(
        "/customers/me", headers={"Authorization": "Bearer this.is.not.a.jwt"}
    )
    assert res.status_code == 401


async def test_expired_token_is_rejected(client, db):
    user = await make_user(db)
    token = _encode(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),  # already expired
        }
    )
    res = await client.get("/customers/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_token_signed_with_wrong_secret_is_rejected(client, db):
    user = await make_user(db)
    forged = jwt.encode(
        {"sub": str(user.id), "role": user.role.value,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret",
        algorithm=settings.jwt_algorithm,
    )
    res = await client.get("/customers/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


async def test_token_missing_role_claim_is_rejected(client, db):
    # A structurally valid, correctly signed token that's missing the `role`
    # claim must still be rejected — the payload is incomplete.
    user = await make_user(db)
    token = _encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    )
    res = await client.get("/customers/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
