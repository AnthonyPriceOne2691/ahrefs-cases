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
    except Exception as exc:
        # Причина печатается, а не глотается: «база не поднята» и «неверный DSN»
        # выглядят одинаково как пропуск теста, но лечатся по-разному.
        print(f"проба базы не прошла ({type(exc).__name__}): {exc}")
        return False
    else:
        return True
    finally:
        await engine.dispose()
        # Дать циклу закрыть транспорт asyncpg — см. `storage.session`.
        for _ in range(3):
            await asyncio.sleep(0)


@pytest.fixture(scope="session")
def db_available() -> bool:
    """Доступна ли дев-база.

    Недоступна — тесты на миграции и health пропускаются с явной причиной, а не
    тихо считаются пройденными: пропуск и успех обязаны различаться в выводе.
    """
    from ahrefs_cases import config

    return asyncio.run(_probe_database(config.storage.database_url))


@pytest.fixture
def needs_db(db_available: bool) -> None:
    """Пропуск, а не падение, когда базы нет. Уборки за собой нет — поэтому
    `return`, а не `yield`: фикстура-генератор без teardown вводит в заблуждение."""
    if not db_available:
        pytest.skip(_SKIP_REASON)


@pytest.fixture(autouse=True)
def dispose_engine_after_test() -> Iterator[None]:
    """Закрывать пул после каждого теста.

    Движок кэшируется на процесс (`lru_cache` в `storage.session`), и без этого
    соединение к postgres доживает до выхода интерпретатора: сокет закрывает
    сборщик мусора, и `filterwarnings = ["error"]` ловит это как
    `PytestUnraisableExceptionWarning`. Утечка настоящая — просто её видно не в
    тесте, а на финализации, поэтому обычный прогон её не замечал.

    Второй эффект: тест, подменивший DSN (A3), не оставляет за собой движок с
    мёртвым адресом следующему тесту.
    """
    from ahrefs_cases import storage

    yield
    asyncio.run(storage.dispose_engine())
