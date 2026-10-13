"""Alembic Environment: async-движок из app.config (SQLite dev / PostgreSQL prod)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)  # type: ignore[no-untyped-call]

target_metadata = Base.metadata

# URL — единственный источник истины: .env → app.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def include_object(
    obj, name, type_, reflected, compare_to
):
    """Не трогаем pgvector-таблицы, созданные вне alembic."""
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=(connection.dialect.name == "sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    db_url = config.get_main_option("sqlalchemy.url")
    if db_url and db_url.startswith("sqlite"):
        from app.db.base import _ensure_sqlite_dir
        _ensure_sqlite_dir(db_url)

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())