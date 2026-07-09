from fastapi import FastAPI

from app.routers import agent, customers, inventory, orders, products, subscriptions

app = FastAPI(title="Farm Products Agents API")

app.include_router(customers.router)
app.include_router(subscriptions.router)
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(agent.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
