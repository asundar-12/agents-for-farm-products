from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# Neon's pooled connection (the -pooler endpoint) runs PgBouncer in "transaction
# mode." In transaction mode, asyncpg's server-side prepared statements can leak
# across clients that share the same underlying connection, causing cryptic
# "prepared statement already exists" errors under load. asyncpg avoids this
# if we disable its prepared-statement cache. This is exactly the kind of thing
# that works fine in local dev against a direct connection and then breaks in
# whatever environment actually uses the pooled URL — so we disable it
# unconditionally rather than only in prod.
#
# poolclass=NullPool: don't hold a local connection pool at all — every checkout
# opens a fresh asyncpg connection, every checkin closes it. Two reasons:
# (1) Neon's own pooler is already doing the actual connection multiplexing, so
#     a local SQLAlchemy pool on top of it would just be double-pooling.
# (2) The agent's terminal loop calls Agent(...) synchronously, and each call
#     spins up its own asyncio.run() — a brand-new event loop every turn. A
#     persistent pool holds asyncpg connections tied to whichever event loop
#     created them; when that loop closes and a later turn's new loop tries to
#     reuse/clean up the old connection, asyncpg raises "Event loop is closed."
#     NullPool has no cross-call state to go stale, so this can't happen.
engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
