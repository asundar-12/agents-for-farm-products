"""Shared test fixtures for the Harmony Acres API.

Design notes for anyone reading these tests for the first time:

- We run against a *real* Postgres database (`harmony_acres_test`), not SQLite,
  because the models lean on Postgres-only features: native ENUM types, a
  UUID column type, and a partial unique index (`postgresql_where=...`). SQLite
  would silently ignore or fail on those, so a passing test wouldn't prove much.

- The app reads its settings once, at import time, and caches them. So we set
  the test database URL and JWT secret in the environment *before* importing
  anything from `app`. That's why the os.environ block sits at the very top,
  above the app imports.

- Each test gets a freshly created schema and drops it afterwards. That's the
  simplest reliable isolation: no test can see another's rows, and there's no
  shared state to reset by hand.
"""

import os

# --- Must run before any `app.*` import (settings are cached at import time) ---
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://arjunsundaram@localhost:5432/harmony_acres_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# Importing the models package registers every table on Base.metadata, which
# create_all/drop_all need to see the whole schema.
import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = get_settings().database_url


@pytest_asyncio.fixture
async def _schema():
    """Create a clean schema for one test, drop it afterwards.

    drop_all first clears anything a previous crashed run left behind (Postgres
    ENUM types in particular linger and would make create_all fail with
    'type already exists'). Everything here is function-scoped so a single event
    loop owns the engine for the whole test — mixing loop scopes with async
    SQLAlchemy is a classic source of 'attached to a different loop' errors.
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    # Point the app's get_db dependency at the test database for the duration of
    # this test, so API requests read/write the same schema we seed.
    async def _override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    try:
        yield TestSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db(_schema) -> AsyncSession:
    """A session for the test itself to seed rows and assert on the DB directly."""
    async with _schema() as session:
        yield session


@pytest_asyncio.fixture
async def client(_schema) -> AsyncClient:
    """An HTTP client that drives the real FastAPI app in-process (no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
