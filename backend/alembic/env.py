"""
Alembic environment configuration.

Loads the application Settings to build the database URL,
and imports all ORM models so Alembic autogenerate can detect changes.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the backend/ directory is on sys.path so `app.*` imports work
# when running `alembic` from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

# Import all model modules so Base.metadata is fully populated.
from app.models import (  # noqa: F401  # noqa: E402, F401  # noqa: E402, F401
    chunk,
    company,
    criterion,
    document,
    financial,
    message,
    profile,
    result,
    section,
    session,
)
from app.models.base import Base

# ── Alembic Config ───────────────────────────────────────────────

config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the application's sync URL
try:
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.sync_database_url)
except Exception:
    # Fall back to alembic.ini default if Settings can't load
    # (e.g., missing env vars in CI — the URL in alembic.ini will be used)
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generate SQL without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
