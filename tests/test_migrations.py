"""Миграции: цикл upgrade → downgrade → upgrade.

Пример приёмки A1. Тест разрушает содержимое базы, поэтому включается флагом:
молча снести дев-базу разработчика — не то поведение, которое стоит получать
за запуск `pytest`.
"""

from __future__ import annotations

import os
import pathlib

import pytest
from alembic import command
from alembic.config import Config

_ROOT = pathlib.Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not os.environ.get("MIGRATION_CYCLE_TEST"),
    reason="разрушает базу; включается MIGRATION_CYCLE_TEST=<имя базы> (в CI база одноразовая)",
)


@pytest.fixture(autouse=True)
def destructible_database() -> None:
    """Разрушать можно только базу, названную по имени: `MIGRATION_CYCLE_TEST=<имя базы>`.

    Прежде хватало `MIGRATION_CYCLE_TEST=1`, и 08.10.2026 цикл «вверх, вниз до пустой схемы,
    вверх» прошёл по дев-базе `cases`: её строки ушли вместе с таблицами, восстанавливали из
    копии стенда. Имя вместо единицы — согласие на разрушение именно этой базы; не совпало —
    отказ громко, а не тихий пропуск: тест, которого ждали, должен сказать, почему не шёл (L73).
    """
    from sqlalchemy.engine import make_url

    from ahrefs_cases import config

    named = os.environ.get("MIGRATION_CYCLE_TEST", "")
    target = make_url(config.storage.database_url).database
    if named != target:
        pytest.fail(
            f"цикл миграций разрушает базу «{target}», а MIGRATION_CYCLE_TEST называет «{named}»: "
            "укажите имя базы, которую разрешаете разрушить, или направьте DATABASE_URL на временную"
        )


@pytest.fixture
def alembic_config() -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    return cfg


def _enum_types(url: str) -> list[str]:
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _query() -> list[str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT typname FROM pg_type WHERE typtype = 'e' ORDER BY 1")
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(_query())


def _run_sql(url: str, *statements: str) -> list[tuple[object, ...]]:
    """Выполнить операторы по порядку; вернуть строки последнего."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _go() -> list[tuple[object, ...]]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                result = None
                for statement in statements:
                    result = await conn.execute(text(statement))
                return [tuple(row) for row in result] if result and result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(_go())


_GEO_ROWS = (
    "INSERT INTO projects (domain, target_mode, period_start, period_end, niche, geo, "
    "service_type, client, owner, publishable, notes, status) VALUES "
    "('several.migration.example', 'SUBDOMAINS', '2025-01-01', '2025-12-01', 'x', 'DE,AT,CH', "
    "'seo', 'c', 'o', true, '', 'NEW'), "
    "('world.migration.example', 'SUBDOMAINS', '2025-01-01', '2025-12-01', 'x', 'WW', "
    "'seo', 'c', 'o', true, '', 'NEW')"
)
_GEO_READ = "SELECT domain, geo FROM projects WHERE domain LIKE '%.migration.example' ORDER BY 1"
_GEO_DROP = "DELETE FROM projects WHERE domain LIKE '%.migration.example'"


def test_geo_downgrade_keeps_the_country_ahrefs_counted_by(
    alembic_config: Config, needs_db: None
) -> None:
    """M9: откат колонки в две буквы оставляет страну, по которой считал сбор, —
    первую из списка; весь мир — пустое гео: прежний код ровно тогда и спрашивал
    Ahrefs без страны."""
    from ahrefs_cases import config

    url = config.storage.database_url
    command.upgrade(alembic_config, "head")
    _run_sql(url, _GEO_DROP, _GEO_ROWS)

    command.downgrade(alembic_config, "a8b9c0d1e2f3")  # pragma: allowlist secret
    rows = _run_sql(url, _GEO_READ)
    command.upgrade(alembic_config, "head")
    _run_sql(url, _GEO_DROP)

    assert rows == [("several.migration.example", "DE"), ("world.migration.example", "")]


_POINT_PROJECTS = (
    "INSERT INTO projects (domain, target_mode, period_start, period_end, niche, geo, "
    "service_type, client, owner, publishable, notes, status) VALUES "
    "('us.rows.migration.example', 'SUBDOMAINS', '2025-01-01', '2025-12-01', 'x', 'US,CA', "
    "'seo', 'c', 'o', true, '', 'NEW'), "
    "('world.rows.migration.example', 'SUBDOMAINS', '2025-01-01', '2025-12-01', 'x', 'WW', "
    "'seo', 'c', 'o', true, '', 'NEW')"
)
_POINT_ROWS = (
    "INSERT INTO metric_points (project_id, metric, point_date, value, source) "
    "SELECT id, 'ORG_TRAFFIC', DATE '2025-01-01', 100, 'FIXTURE' FROM projects "
    "WHERE domain LIKE '%.rows.migration.example'"
)
_POINT_READ = (
    "SELECT project.domain, point.country FROM metric_points AS point "
    "JOIN projects AS project ON project.id = point.project_id "
    "WHERE project.domain LIKE '%.rows.migration.example' ORDER BY 1"
)
_POINT_COLUMN = (
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name = 'metric_points' AND column_name = 'country'"
)
_POINT_DROP = "DELETE FROM projects WHERE domain LIKE '%.rows.migration.example'"
_BEFORE_COUNTRY = "d1e2f3a4b5c6"  # pragma: allowlist secret


def test_bought_points_learn_the_country_of_their_project(
    alembic_config: Config, needs_db: None
) -> None:
    """M80: купленным точкам проставлена первая страна проекта, у «всего мира» — пусто;
    откат убирает колонку."""
    from ahrefs_cases import config

    url = config.storage.database_url
    command.upgrade(alembic_config, "head")
    _run_sql(url, _POINT_DROP)
    command.downgrade(alembic_config, _BEFORE_COUNTRY)
    _run_sql(url, _POINT_PROJECTS, _POINT_ROWS)

    command.upgrade(alembic_config, "head")
    rows = _run_sql(url, _POINT_READ)
    command.downgrade(alembic_config, _BEFORE_COUNTRY)
    column = _run_sql(url, _POINT_COLUMN)
    command.upgrade(alembic_config, "head")
    _run_sql(url, _POINT_DROP)

    assert rows == [("us.rows.migration.example", "US"), ("world.rows.migration.example", "")]
    assert column == []


def test_upgrade_downgrade_upgrade_cycle(alembic_config: Config, needs_db: None) -> None:
    """A1: три шага подряд без ошибок, и после downgrade не остаётся ENUM-типов.

    Проверка типов здесь не педантизм: autogenerate создаёт их неявно и не
    удаляет в downgrade, из-за чего цикл падал на `DuplicateObject` — миграция
    «работала» ровно один раз. Убрать эту проверку значит вернуть тот же дефект.
    """
    from ahrefs_cases import config

    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    assert _enum_types(config.storage.database_url) == []

    command.upgrade(alembic_config, "head")
