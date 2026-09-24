"""Советующие замки Postgres: кто сейчас пишет строки проектов.

**Постановка прогона** — «нет активных» и строка прогона неделимы. **Работа** —
задача очереди и пересчёт порогов пишут строки всех проектов; удаление проекта
посреди неё роняет её на внешнем ключе. Замок, а не вопрос к очереди «жива ли
задача»: при `QUEUE_BACKEND=inline` задачи в RQ нет вовсе, а замок держит само
соединение работы — умерла задача, умер и замок.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from ahrefs_cases import config

START_LOCK_KEY = 4_242_001
WORK_LOCK_KEY = 4_242_002


async def hold_start(session: AsyncSession) -> None:
    """Замок постановки до конца транзакции: второй прогон и удаление ждут её."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": START_LOCK_KEY})


async def hold_work(session: AsyncSession) -> None:
    """Разделяемый замок работы до конца транзакции — работе в одном запросе."""
    await session.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": WORK_LOCK_KEY})


async def work_is_idle(session: AsyncSession) -> bool:
    """Взять замок работы исключительно, если свободен. Не ждёт: запрос, вставший
    за многочасовым прогоном, упал бы по таймауту прокси, не сказав чего ждал."""
    taken = await session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": WORK_LOCK_KEY}
    )
    return bool(taken)


@asynccontextmanager
async def work_lock() -> AsyncIterator[None]:
    """Держать разделяемый замок работы, пока идёт задача, — хоть часами.

    Замок сессионный, поэтому соединение своё и без пула (вернувшись в пул, оно
    унесло бы замок в чужой запрос) и без открытой транзакции (`AUTOCOMMIT`).
    Снимается закрытием соединения — и смертью процесса.
    """
    engine = create_async_engine(
        config.storage.database_url, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_advisory_lock_shared(:key)"), {"key": WORK_LOCK_KEY}
            )
            yield
    finally:
        await engine.dispose()
        for _ in range(3):  # дать циклу закрыть транспорт asyncpg — см. `storage.session`
            await asyncio.sleep(0)
