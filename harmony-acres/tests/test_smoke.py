"""Sanity check that the fixtures wire up: DB seeding + app requests both work."""

from tests.factories import auth_headers, make_user


async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_seed_and_authed_request(client, db):
    user = await make_user(db)
    res = await client.get("/customers/me", headers=auth_headers(user))
    assert res.status_code == 200
    assert res.json()["email"] == user.email
