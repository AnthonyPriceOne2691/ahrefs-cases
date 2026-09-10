"""Общие фикстуры. Ни один тест не ходит в сеть и не берёт живой ключ Ahrefs."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest

# Тесты не читают .env разработчика: иначе результат зависит от чужой машины.
os.environ.setdefault("AHREFS_PROVIDER", "fixture")

_SKIP_REASON = "дев-база недоступна: docker compose -f docker-compose.dev.yml up -d postgres"


async def _probe_database(url: str) -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 -- проба: любой отказ означает «базы нет»
        # Причина печатается, а не глотается: «база не поднята» и «неверный DSN»
        # выглядят одинаково как пропуск теста, но лечатся по-разному.
        print(f"проба базы не прошла ({type(exc).__name__}): {exc}")
        return False
    else:
        return True
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def db_available() -> bool:
    """Доступна ли дев-база.

    Недоступна — тесты на миграции и health пропускаются с явной причиной, а не
    тихо считаются пройденными: пропуск и успех обязаны различаться в выводе.
    """
    from ahrefs_cases import config

    return asyncio.run(_probe_database(config.storage.database_url))


@pytest.fixture
def needs_db(db_available: bool) -> Iterator[None]:
    if not db_available:
        pytest.skip(_SKIP_REASON)
    yield
