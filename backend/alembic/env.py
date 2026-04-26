"""
Cyrus — Alembic Environment Configuration

Alembic is the database migration tool for SQLAlchemy.
Every time you add a column or table, you run:
  alembic revision --autogenerate -m "describe the change"
  alembic upgrade head

This applies the change to the real database without losing existing data.
"""

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, engine_from_config
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Load all models so Alembic can see them for autogenerate
from app.database import Base
import app.models  # noqa — must import __init__.py to trigger all model registrations

from app.config import get_settings

settings = get_settings()

# Alembic configuration object
config = context.config

# Set database URL from our settings (overrides alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", ""))

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic about our table metadata (so it can detect changes)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a real database connection.
    Used for generating SQL scripts.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations with a real database connection.
    This is the default mode used by `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
