from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin, agent, customers, cycles, orders, products, subscriptions

settings = get_settings()

app = FastAPI(title="Farm Product Agent API")

# Only the configured frontend origins may call this API from a browser. Set
# cors_allow_origins to the Amplify domain in production (see config.py).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
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
