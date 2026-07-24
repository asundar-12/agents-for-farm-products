from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, agent, customers, cycles, orders, products, subscriptions

app = FastAPI(title="Farm Product Agent API")

# Allows the local static chat UI (served from a different origin/port, e.g.
# a plain `python -m http.server` or file://) to call this API directly from
# the browser. Tighten allow_origins to the real frontend origin before prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(subscriptions.router)
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(cycles.router)
app.include_router(admin.router)
app.include_router(agent.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
