"""System / end-to-end tests driven entirely through the HTTP API.

The first test walks one product from a customer's order all the way through the
farm-side lifecycle to a closed week, hitting the real routers, services, and
database at each step. The second exercises the assistant endpoint with the
Bedrock AgentCore call mocked out — we test our plumbing, not AWS.
"""

from unittest.mock import MagicMock, patch

import app.routers.agent as agent_module
from app.models.customer import UserRole
from tests.factories import auth_headers, make_user


async def _register_and_login(client, email="flow@test.com", password="password123"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Flow Customer"},
    )
    assert reg.status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_full_week_lifecycle_end_to_end(client, db):
    # A product to order (seeded directly; there's no admin catalog endpoint).
    from tests.factories import make_product

    product = await make_product(db, price="6.50")

    # 1. Customer registers, logs in, builds and submits an order.
    cust_headers = await _register_and_login(client)
    await client.put(
        "/orders/draft/items",
        headers=cust_headers,
        json={"product_id": str(product.id), "quantity": 4},
    )
    submit = await client.post("/orders/draft/submit", headers=cust_headers)
    assert submit.status_code == 200 and submit.json()["status"] == "submitted"

    # 2. Admin looks at the dashboard — the order should be counted.
    admin = await make_user(db, role=UserRole.admin, email="admin@farm.test")
    ah = auth_headers(admin)
    dash = await client.get("/admin/dashboard", headers=ah)
    assert dash.status_code == 200
    cycle_id = dash.json()["cycle"]["id"]
    assert dash.json()["order_count"] == 1

    # 3. Aggregate -> the shopping list shows 4 units of the product.
    agg = await client.post(f"/admin/cycles/{cycle_id}/aggregate", headers=ah)
    assert agg.status_code == 200
    line = next(l for l in agg.json()["lines"] if l["product_id"] == str(product.id))
    assert line["total_quantity"] == 4

    # 4. Walk the rest of the lifecycle.
    assert (await client.post(f"/admin/cycles/{cycle_id}/approve", headers=ah)).status_code == 200
    assert (await client.post(f"/admin/cycles/{cycle_id}/mark-ordered", headers=ah)).status_code == 200
    assert (await client.post(f"/admin/cycles/{cycle_id}/mark-received", headers=ah, json={})).status_code == 200
    closed = await client.post(f"/admin/cycles/{cycle_id}/close", headers=ah)
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


async def test_illegal_admin_transition_is_rejected_over_http(client, db):
    # Fresh open cycle (created on first dashboard read). Jumping straight to
    # "close" must be refused end-to-end, not just in the service unit tests.
    admin = await make_user(db, role=UserRole.admin, email="admin@farm.test")
    ah = auth_headers(admin)
    dash = await client.get("/admin/dashboard", headers=ah)
    cycle_id = dash.json()["cycle"]["id"]

    res = await client.post(f"/admin/cycles/{cycle_id}/close", headers=ah)
    assert res.status_code == 422


async def test_assistant_chat_with_bedrock_mocked(client, db):
    # Replace the module-level AgentCore client with a fake that streams back
    # one SSE delta frame, so /agent/chat returns the assembled text without any
    # AWS call.
    user = await make_user(db)

    fake_body = MagicMock()
    fake_body.iter_lines.return_value = [b'data: {"delta": "Hello from the farm"}']
    fake_client = MagicMock()
    fake_client.invoke_agent_runtime.return_value = {"response": fake_body}

    with patch.object(agent_module, "_agentcore_client", fake_client):
        res = await client.post(
            "/agent/chat", headers=auth_headers(user), json={"message": "hi"}
        )

    assert res.status_code == 200
    assert res.json()["result"] == "Hello from the farm"
    assert fake_client.invoke_agent_runtime.called
