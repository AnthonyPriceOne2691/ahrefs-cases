"""Alembic: адрес базы и метаданные берутся из проекта, а не из alembic.ini.

Причина: DSN, записанный в двух местах, разъезжается молча — и обычно это
обнаруживается миграцией, применённой не к той базе.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from ahrefs_cases import config as app_config
from ahrefs_cases.storage.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", app_config.storage.database_url)
target_metadata = Base.metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=app_config.storage.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    section = config.get_section(config.config_ini_section, {})
    engine = async_engine_from_config(section, prefix="sqlalchemy.")
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()
        # Отдать циклу одну итерацию, чтобы транспорт asyncpg успел закрыться.
        # `dispose()` закрывает соединение, а закрытие транспорта asyncpg ставит
        # в цикл `call_soon` — и `asyncio.run()` внутри alembic закрывает цикл
        # раньше, чем колбэк выполнится. Наружу это вылезает `ResourceWarning:
        # unclosed transport` при сборке мусора, то есть уже вне теста: обычный
        # прогон его не замечал, поймал строгий рантайм (`filterwarnings=error`).
        await asyncio.sleep(0)


def run_migrations_online() -> None:
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
