"""Customer order workflow (business rule 1, as this app actually models it).

The order itself only moves draft -> submitted; the Approved/Ordered/Received/
Closed states your spec lists live on the *weekly cycle* (see
test_cycle_lifecycle.py). The rules enforced on the order are:
  - you can't submit an empty draft
  - you can't submit without a pickup location
  - once submitted, you can't submit again or keep editing (no double-count)
  - a product the farm isn't carrying can't be added
  - ordering is locked once the cycle's deadline has passed
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.weekly import CycleStatus
from app.services import cycle_service
from tests.factories import auth_headers, make_cycle, make_product, make_user


async def _add_item(client, user, product, qty):
    return await client.put(
        "/orders/draft/items",
        headers=auth_headers(user),
        json={"product_id": str(product.id), "quantity": qty},
    )


# --- Happy path --------------------------------------------------------------


async def test_submit_flow_happy_path(client, db):
    user = await make_user(db)
    product = await make_product(db, price="6.50")

    assert (await _add_item(client, user, product, 2)).status_code == 200

    patched = await client.patch(
        "/orders/draft", headers=auth_headers(user), json={"pickup_location": "Farm stand"}
    )
    assert patched.status_code == 200

    submitted = await client.post("/orders/draft/submit", headers=auth_headers(user))
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["total_amount"] == "13.00"  # 2 * 6.50


# --- Negative / edge cases ---------------------------------------------------


async def test_cannot_submit_empty_draft(client, db):
    user = await make_user(db)
    # Touch the draft so it exists, but add nothing.
    await client.get("/orders/draft", headers=auth_headers(user))
    res = await client.post("/orders/draft/submit", headers=auth_headers(user))
    assert res.status_code == 422


async def test_cannot_submit_without_pickup_location(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await _add_item(client, user, product, 1)  # item present, but no pickup set
    res = await client.post("/orders/draft/submit", headers=auth_headers(user))
    assert res.status_code == 422


async def test_cannot_submit_twice(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await _add_item(client, user, product, 1)
    await client.patch(
        "/orders/draft", headers=auth_headers(user), json={"pickup_location": "Farm stand"}
    )
    assert (await client.post("/orders/draft/submit", headers=auth_headers(user))).status_code == 200

    # Second submit must be refused — otherwise the customer double-counts.
    second = await client.post("/orders/draft/submit", headers=auth_headers(user))
    assert second.status_code == 422


async def test_editing_is_blocked_after_submit(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await _add_item(client, user, product, 1)
    await client.patch(
        "/orders/draft", headers=auth_headers(user), json={"pickup_location": "Farm stand"}
    )
    await client.post("/orders/draft/submit", headers=auth_headers(user))

    # Trying to change quantities after submitting is rejected.
    res = await _add_item(client, user, product, 5)
    assert res.status_code == 422


async def test_cannot_add_unavailable_product(client, db):
    user = await make_user(db)
    product = await make_product(db, is_available=False)
    res = await _add_item(client, user, product, 1)
    assert res.status_code == 422


async def test_negative_quantity_is_rejected(client, db):
    user = await make_user(db)
    product = await make_product(db)
    res = await _add_item(client, user, product, -1)
    assert res.status_code == 422


async def test_zero_quantity_removes_item(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await _add_item(client, user, product, 3)
    await _add_item(client, user, product, 0)  # remove it
    draft = await client.get("/orders/draft", headers=auth_headers(user))
    assert draft.status_code == 200
    assert draft.json()["items"] == []


# --- Deadline lock (service-level: the API always hands out the open week) ----


def test_cycle_is_open_before_deadline():
    from app.models.weekly import WeeklyCycle

    cycle = WeeklyCycle(
        week_start=datetime.now(timezone.utc).date(),
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=1),
        delivery_date=datetime.now(timezone.utc).date(),
        status=CycleStatus.open,
    )
    assert cycle_service.is_open(cycle) is True


async def test_ordering_locked_after_deadline(db):
    # An open cycle whose deadline has already passed is closed to edits.
    cycle = await make_cycle(
        db,
        status=CycleStatus.open,
        deadline=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert cycle_service.is_open(cycle) is False
    with pytest.raises(HTTPException) as exc:
        cycle_service.assert_open(cycle)
    assert exc.value.status_code == 422


async def test_locked_status_closes_ordering_even_before_deadline(db):
    # Admin locking early closes the window regardless of the clock.
    cycle = await make_cycle(
        db,
        status=CycleStatus.locked,
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert cycle_service.is_open(cycle) is False
