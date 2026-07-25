"""Role-based access control (business rule 2).

This app has two roles: customer and admin (there is no Accounting role). The
rules under test:
  - admin-only endpoints reject a customer token
  - a customer cannot read another customer's order
  - the legitimate owner / correct role still gets through (happy path)
"""

from app.models.customer import UserRole
from tests.factories import (
    auth_headers,
    make_cycle,
    make_product,
    make_submitted_order,
    make_user,
)


# --- Admin-only endpoints ----------------------------------------------------


async def test_admin_endpoint_allows_admin(client, db):
    admin = await make_user(db, role=UserRole.admin, email="admin@farm.test")
    res = await client.get("/admin/dashboard", headers=auth_headers(admin))
    assert res.status_code == 200


async def test_admin_endpoint_rejects_customer(client, db):
    customer = await make_user(db, role=UserRole.customer)
    res = await client.get("/admin/dashboard", headers=auth_headers(customer))
    assert res.status_code == 403


async def test_admin_customer_list_rejects_customer(client, db):
    customer = await make_user(db, role=UserRole.customer)
    res = await client.get("/admin/customers", headers=auth_headers(customer))
    assert res.status_code == 403


# --- Ownership: a customer can't touch another customer's order --------------


async def test_customer_can_read_own_order(client, db):
    user = await make_user(db)
    cycle = await make_cycle(db)
    product = await make_product(db)
    order = await make_submitted_order(db, user=user, cycle=cycle, product=product, quantity=2)

    res = await client.get(f"/orders/{order.id}", headers=auth_headers(user))
    assert res.status_code == 200
    assert res.json()["id"] == str(order.id)


async def test_customer_cannot_read_another_customers_order(client, db):
    owner = await make_user(db, email="owner@test.com")
    intruder = await make_user(db, email="intruder@test.com")
    cycle = await make_cycle(db)
    product = await make_product(db)
    order = await make_submitted_order(db, user=owner, cycle=cycle, product=product, quantity=2)

    res = await client.get(f"/orders/{order.id}", headers=auth_headers(intruder))
    assert res.status_code == 403


async def test_admin_can_reach_customer_endpoint_with_valid_token(client, db):
    # An admin is still a valid authenticated user for shared endpoints; role
    # gating only restricts the admin-only routes, not the reverse.
    admin = await make_user(db, role=UserRole.admin, email="admin2@farm.test")
    res = await client.get("/customers/me", headers=auth_headers(admin))
    assert res.status_code == 200
    assert res.json()["role"] == "admin"
