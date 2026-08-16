"""One subscription per product, per customer.

A second standing order for a product a customer already subscribes to is
always a mistake — it silently doubles what shows up on the delivery. The rule
has two halves: no repeated product inside a single subscription, and no
product spread across two of the customer's subscriptions. Cancelled
subscriptions are exempt, since they never generate a delivery.
"""

from datetime import date, timedelta

from app.models.subscription import SubscriptionStatus
from tests.factories import auth_headers, make_product, make_subscription, make_user


def _next_wednesday() -> date:
    today = date.today()
    return today + timedelta(days=(2 - today.weekday()) % 7 or 7)


async def _create(client, user, products_and_qty):
    return await client.post(
        "/subscriptions",
        headers=auth_headers(user),
        json={
            "frequency": "weekly",
            "next_delivery_date": _next_wednesday().isoformat(),
            "items": [{"product_id": str(p.id), "quantity": q} for p, q in products_and_qty],
        },
    )


async def test_create_rejects_same_product_twice_in_one_payload(client, db):
    user = await make_user(db)
    product = await make_product(db)

    res = await _create(client, user, [(product, 1), (product, 2)])

    assert res.status_code == 422
    assert "listed twice" in res.json()["detail"]


async def test_create_rejects_product_already_on_another_subscription(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await make_subscription(
        db, user=user, product=product, quantity=1, next_delivery_date=_next_wednesday()
    )

    res = await _create(client, user, [(product, 3)])

    assert res.status_code == 422
    assert "already have a subscription" in res.json()["detail"]


async def test_paused_subscription_still_blocks_a_duplicate(client, db):
    # A pause is temporary — resuming it would resurrect the duplicate.
    user = await make_user(db)
    product = await make_product(db)
    await make_subscription(
        db,
        user=user,
        product=product,
        quantity=1,
        next_delivery_date=_next_wednesday(),
        status=SubscriptionStatus.paused,
    )

    assert (await _create(client, user, [(product, 1)])).status_code == 422


async def test_cancelled_subscription_does_not_block_resubscribing(client, db):
    user = await make_user(db)
    product = await make_product(db)
    await make_subscription(
        db,
        user=user,
        product=product,
        quantity=1,
        next_delivery_date=_next_wednesday(),
        status=SubscriptionStatus.cancelled,
    )

    assert (await _create(client, user, [(product, 1)])).status_code == 201


async def test_another_customer_subscribing_to_the_same_product_is_fine(client, db):
    product = await make_product(db)
    first = await make_user(db)
    second = await make_user(db)
    await make_subscription(
        db, user=first, product=product, quantity=1, next_delivery_date=_next_wednesday()
    )

    assert (await _create(client, second, [(product, 1)])).status_code == 201


async def test_update_can_keep_its_own_product(client, db):
    # Editing a subscription must not clash with the rows it is replacing.
    user = await make_user(db)
    product = await make_product(db)
    created = await _create(client, user, [(product, 1)])
    subscription_id = created.json()["id"]

    res = await client.patch(
        f"/subscriptions/{subscription_id}",
        headers=auth_headers(user),
        json={"items": [{"product_id": str(product.id), "quantity": 5}]},
    )

    assert res.status_code == 200
    assert res.json()["items"][0]["quantity"] == 5


async def test_update_rejects_a_product_from_another_subscription(client, db):
    user = await make_user(db)
    milk = await make_product(db, name="Whole Milk (1 Gal)")
    eggs = await make_product(db, name="Dozen Eggs")
    await make_subscription(db, user=user, product=eggs, quantity=1, next_delivery_date=_next_wednesday())
    created = await _create(client, user, [(milk, 1)])

    res = await client.patch(
        f"/subscriptions/{created.json()['id']}",
        headers=auth_headers(user),
        json={"items": [{"product_id": str(eggs.id), "quantity": 1}]},
    )

    assert res.status_code == 422
    assert "already have a subscription" in res.json()["detail"]
