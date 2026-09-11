"""Общие фикстуры. Ни один тест не ходит в сеть и не берёт живой ключ Ahrefs."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from functools import lru_cache

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Тесты не читают .env разработчика: иначе результат зависит от чужой машины.
os.environ.setdefault("AHREFS_PROVIDER", "fixture")

_UP_COMMAND = "docker compose -f docker-compose.dev.yml up -d postgres"
_SKIP_REASON = f"дев-база недоступна: {_UP_COMMAND}"
_ALLOW_NO_DB = "AHREFS_TESTS_ALLOW_NO_DB"
_DB_FIXTURES = frozenset({"needs_db", "migrated_db", "db_session"})


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


@lru_cache(maxsize=1)
def _database_reachable() -> bool:
    """Проба базы — **один раз на прогон**, а не на каждый тест.

    Кэш на функции, а не фикстура, потому что ответ нужен ещё и на этапе сбора
    тестов, куда фикстуры не дотягиваются.
    """
    from ahrefs_cases import config

    return asyncio.run(_probe_database(config.storage.database_url))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Нет базы, а тесты её требуют — остановить прогон, а не пропустить их.

    До этого `pytest` без дев-базы печатал «253 passed, 154 skipped» и возвращал
    ноль. Формально честно — пропуск и успех в выводе различаются, — а читается
    как «всё хорошо»: чтобы понять, что проверена треть, нужно заметить второе
    число. Тот же класс, что L8, L58 и L68 («зелёный по причине окружения»),
    только здесь окружение не подменяет данные, а **убирает проверки**.

    Останавливаемся один раз: причина одна, и сотня одинаковых красных спрятала
    бы её среди самих себя. Остановка касается только прогонов, где такие тесты
    действительно выбраны: чистые модульные тесты базы не требуют и докера
    требовать не должны.

    `AHREFS_TESTS_ALLOW_NO_DB=1` возвращает прежний пропуск. Пропуск сам по себе
    не зло — злом было умолчание; набранная руками переменная делает выбор
    видимым.
    """
    if os.getenv(_ALLOW_NO_DB) == "1":
        return
    if not any(_DB_FIXTURES & set(item.fixturenames) for item in items):
        return
    if _database_reachable():
        return
    pytest.exit(
        f"прогон остановлен: {_SKIP_REASON}. "
        f"Пропустить эти тесты осознанно: {_ALLOW_NO_DB}=1 pytest",
        returncode=1,
    )


@pytest.fixture(scope="session")
def db_available() -> bool:
    """Доступна ли дев-база. К этому моменту прогон уже остановлен, если она
    нужна и недоступна, — значит `False` здесь означает выбранный человеком
    `AHREFS_TESTS_ALLOW_NO_DB`."""
    return _database_reachable()


@pytest.fixture
def needs_db(db_available: bool) -> None:
    """Пропуск, а не падение, когда базы нет **и человек этого попросил**.

    Уборки за собой нет — поэтому `return`, а не `yield`: фикстура-генератор
    без teardown вводит в заблуждение.
    """
    if not db_available:
        pytest.skip(_SKIP_REASON)


@pytest.fixture(autouse=True)
def engine_without_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Движок приложения в тестах строится без пула соединений.

    `dispose()` закрывает **свободные** соединения; выданное в момент закрытия
    остаётся сиротой и всплывает `ResourceWarning`ом уже при сборке мусора — то
    есть в случайном следующем тесте, а при `filterwarnings = ["error"]` это
    падение там, где ничего не ломали. `NullPool` закрывает соединение при
    возврате, и сирот не остаётся.

    Подменяется **сборка** движка, а не функция `get_engine`: её импортируют по
    имени в нескольких местах, и подмена самой функции оставила бы часть кода
    на старом, пулированном движке — то есть на двух движках сразу.
    """
    from sqlalchemy.ext.asyncio import create_async_engine as real_create
    from sqlalchemy.pool import NullPool

    from ahrefs_cases.storage import session as session_module

    def _without_pool(url: str, **options: object) -> object:
        options.pop("pool_pre_ping", None)
        return real_create(url, poolclass=NullPool, **options)

    monkeypatch.setattr(session_module, "create_async_engine", _without_pool)
    session_module.get_sessionmaker.cache_clear()
    session_module.get_engine.cache_clear()


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


@pytest.fixture
def migrated_db(needs_db: None) -> None:
    """База со применённой схемой.

    Без этой фикстуры тест health'а проходил локально и падал в CI: локальная
    дев-база уже была прогнана `alembic upgrade head`, а в CI она чистая, и
    `alembic_version` там нет. То есть тест был зелёным по причине окружения,
    а не потому, что код верен — ровно тот класс, против которого стоит контур.

    `upgrade head` идемпотентен: на применённой схеме это no-op.
    """
    import pathlib as _pathlib

    from alembic import command
    from alembic.config import Config

    root = _pathlib.Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture
async def db_session(migrated_db: None) -> AsyncIterator[AsyncSession]:
    """Сессия в транзакции, которую откатывают после теста.

    Не `TRUNCATE` после каждого теста и не отдельная база на тест: откат внешней
    транзакции оставляет базу ровно в том состоянии, в каком тест её застал, и
    два теста подряд не видят следов друг друга — даже если один из них упал на
    середине записи.

    Движок здесь **свой**, а не кэшированный `storage.get_engine()`. Общий движок
    создаёт соединения в цикле pytest-asyncio, а автофикстура `dispose_engine`
    закрывает их в новом цикле через `asyncio.run` — закрытие в чужом цикле не
    доходит до сокета, и он всплывает `ResourceWarning`ом на финализации, то есть
    падением сьюта при `filterwarnings = ["error"]`. Создать и закрыть движок в
    одном цикле дешевле, чем чинить порядок фикстур.
    """
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
    from sqlalchemy.ext.asyncio import create_async_engine

    from ahrefs_cases import config

    engine = create_async_engine(config.storage.database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await _truncate_all(connection)
            session = _AsyncSession(bind=connection, expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
                await transaction.rollback()
    finally:
        await engine.dispose()
        # Дать циклу закрыть транспорт asyncpg — см. `storage.session`.
        for _ in range(3):
            await asyncio.sleep(0)


async def _truncate_all(connection: object) -> None:
    """Опустошить таблицы продукта внутри тестовой транзакции.

    Дев-база живёт между прогонами и накапливает следы ручных запусков
    (`scripts/run_collect.py`). Тест, читающий «все проекты», начинал зависеть от
    того, запускал ли кто-то CLI полчаса назад: тот же класс, что тест health'а в
    Ф1, — зелёный или красный по причине окружения, а не по коду.

    `TRUNCATE` выполняется **внутри** внешней транзакции, поэтому откат в конце
    теста возвращает базу к прежнему содержимому: изоляция от чужих данных без
    их уничтожения.
    """
    from sqlalchemy import text

    from ahrefs_cases.storage.models._base import Base

    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # type: ignore[attr-defined]
