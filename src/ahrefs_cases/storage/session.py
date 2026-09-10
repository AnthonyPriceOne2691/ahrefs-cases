"""Асинхронный движок и фабрика сессий.

Кэш вместо глобальных переменных: `lru_cache` даёт тот же единственный движок на
процесс, но без `global` — и сброс становится явной операцией (`cache_clear`),
а не присваиванием None в трёх местах.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ahrefs_cases import config


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Единственный движок на процесс: пул соединений не должен размножаться."""
    return create_async_engine(
        config.storage.database_url,
        echo=config.storage.echo_sql,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI и контекст для воркера: коммит на выходе, rollback на ошибке."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Сколько итераций отдать циклу после закрытия пула. Закрытие транспорта asyncpg
# ставится в цикл через `call_soon`, поэтому мгновенно после `dispose()` оно ещё
# не выполнено: если цикл закрыть сразу (а `asyncio.run` так и делает), сокет
# доживает до сборки мусора и всплывает `ResourceWarning: unclosed transport`
# уже вне теста. Три итерации — с запасом на цепочку колбэков; проверено
# повторными прогонами сьюта под `filterwarnings = ["error"]`.
_TRANSPORT_DRAIN_ITERATIONS = 3


async def dispose_engine() -> None:
    """Закрыть пул, дать транспорту закрыться и сбросить кэш.

    Порядок важен: сначала закрыть соединения, потом забыть движок. Наоборот —
    пул останется висеть без владельца.
    """
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        for _ in range(_TRANSPORT_DRAIN_ITERATIONS):
            await asyncio.sleep(0)
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
