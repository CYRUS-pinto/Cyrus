"""
Cyrus — Database Connection & Session Management

Uses SQLAlchemy async engine.
Supports both PostgreSQL (cloud/full mode) and SQLite (local/offline mode)
based on the DATABASE_URL environment variable.
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    Every table in Cyrus inherits from this.
    It provides the common metadata for Alembic migrations.
    """
    pass


# ─────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────
# The engine is the low-level database connection.
# echo=True in development prints every SQL statement to the console —
# extremely useful for debugging what queries are being run.
engine = create_async_engine(
    settings.database_url,
    echo=(settings.environment == "development"),
    pool_pre_ping=True,          # tests connection before using it (reconnects if stale)
    pool_recycle=3600,           # recycle connections after 1 hour
)

# ─────────────────────────────────────────────────────────────────
# Session Factory
# ─────────────────────────────────────────────────────────────────
# async_sessionmaker creates sessions on demand.
# expire_on_commit=False means we can still access object attributes
# after committing a transaction (important for async code).
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a database session per request.
    Automatically commits on success, rolls back on exception.

    Usage in any FastAPI route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Creates all tables from SQLAlchemy models.
    Called on startup in development. In production, Alembic handles migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
