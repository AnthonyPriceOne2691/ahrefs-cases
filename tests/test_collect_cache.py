"""Кэш серий: с какого месяца докупать историю.

Примеры приёмки: C2 (инкремент от последней точки), C3 (текущий месяц
перезапрашивается, закрытые — нет).

Правило границы проверяется таблицей с явным `now`: `date.today()` внутри
функции сделал бы эти случаи непроверяемыми иначе как подкруткой системных часов.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.cache import (
    Coverage,
    closed_through,
    coverage,
    is_fresh,
    next_date_from,
)
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

WINDOW_FROM = date(2024, 10, 1)
WINDOW_TO = date(2026, 8, 1)
NOW = date(2026, 9, 15)
STAGE1_METRICS = tuple(METRICS_HISTORY.metrics.values())

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)


@pytest.mark.parametrize(
    ("last_point", "expected"),
    [
        (None, WINDOW_FROM),
        (date(2025, 5, 1), date(2025, 6, 1)),
        (date(2024, 12, 1), date(2025, 1, 1)),
        (date(2026, 8, 1), None),
    ],
    ids=["пусто", "по май", "по декабрь", "всё окно собрано"],
)
def test_increment_starts_after_last_point(last_point: date | None, expected: date | None) -> None:
    """C2: докупаем со следующего месяца после последней точки, не с начала окна."""
    known = Coverage(last_point=last_point, fetched_at=datetime(2026, 9, 1, tzinfo=UTC))

    result = next_date_from(
        known, window_from=WINDOW_FROM, window_to=WINDOW_TO, now=NOW, fresh=False
    )

    assert result == expected


def test_closed_month_is_previous_calendar_month() -> None:
    """C3: 15 сентября закрытым считается август, сентябрь — нет."""
    assert closed_through(date(2026, 9, 15)) == date(2026, 8, 31)
    assert closed_through(date(2026, 1, 3)) == date(2025, 12, 31)


def test_current_month_is_refetched_when_stale() -> None:
    """C3: текущий месяц перезапрашивается — он ещё меняется.

    Запрашивается **только он**: `date_from` равен первому числу текущего
    месяца, а не следующему после него и не началу окна.
    """
    known = Coverage(last_point=date(2026, 9, 1), fetched_at=datetime(2026, 9, 1, tzinfo=UTC))

    result = next_date_from(
        known, window_from=WINDOW_FROM, window_to=date(2026, 9, 30), now=NOW, fresh=False
    )

    assert result == date(2026, 9, 1)


def test_current_month_within_ttl_is_not_refetched() -> None:
    """C1/C3: два прогона в один день не платят за текущий месяц дважды.

    Шесть сотрудников из четырёх отделов запускают прогоны в один день
    регулярно; без TTL каждый из них покупал бы один и тот же незакрытый месяц.
    """
    known = Coverage(last_point=date(2026, 9, 1), fetched_at=datetime(2026, 9, 15, tzinfo=UTC))

    result = next_date_from(
        known, window_from=WINDOW_FROM, window_to=date(2026, 9, 30), now=NOW, fresh=True
    )

    assert result is None


def test_freshness_is_measured_in_hours() -> None:
    """TTL считается от `fetched_at`, а не от даты точки."""
    now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

    assert is_fresh(now - timedelta(hours=1), now) is True
    assert is_fresh(now - timedelta(days=3), now) is False
    assert is_fresh(None, now) is False


def test_window_from_wins_over_older_increment() -> None:
    """Инкремент не уводит запрос левее окна проекта.

    Иначе проект с длинной историей в базе и коротким периодом работ
    докупал бы месяцы, которые кейсу не нужны, — и платил за них.
    """
    known = Coverage(last_point=date(2023, 1, 1), fetched_at=datetime(2026, 9, 1, tzinfo=UTC))

    result = next_date_from(
        known, window_from=WINDOW_FROM, window_to=WINDOW_TO, now=NOW, fresh=False
    )

    assert result == WINDOW_FROM


async def _project(session: AsyncSession, domain: str) -> Project:
    row = f"{domain},2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    from sqlalchemy import select

    return (await session.execute(select(Project))).scalars().one()


async def test_coverage_reads_what_is_in_the_database(db_session: AsyncSession) -> None:
    """C2: покрытие берётся из `MetricPoint`, а не из отдельного хранилища."""
    project = await _project(db_session, "cov.example.com")
    for metric in STAGE1_METRICS:
        for month in (1, 2, 3):
            db_session.add(
                MetricPoint(
                    project_id=project.id,
                    metric=metric,
                    point_date=date(2025, month, 1),
                    value=100.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2025, 4, 1, tzinfo=UTC),
                )
            )
    await db_session.flush()

    known = await coverage(db_session, project.id, STAGE1_METRICS, MetricSource.FIXTURE)

    assert known.last_point == date(2025, 3, 1)


async def test_coverage_takes_the_weakest_metric(db_session: AsyncSession) -> None:
    """Покрытие — минимум по метрикам, а не максимум.

    `org_traffic` собран по май, `org_cost` по апрель: докупать надо с апреля.
    Максимум оставил бы `org_cost` без мая навсегда, и дыра выглядела бы как
    отсутствие данных у Ahrefs, а не как наша ошибка.
    """
    project = await _project(db_session, "weak.example.com")
    db_session.add(
        MetricPoint(
            project_id=project.id,
            metric=Metric.ORG_TRAFFIC,
            point_date=date(2025, 5, 1),
            value=100.0,
            source=MetricSource.FIXTURE,
            fetched_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        MetricPoint(
            project_id=project.id,
            metric=Metric.ORG_COST,
            point_date=date(2025, 4, 1),
            value=50.0,
            source=MetricSource.FIXTURE,
            fetched_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()

    known = await coverage(db_session, project.id, STAGE1_METRICS, MetricSource.FIXTURE)

    assert known.last_point == date(2025, 4, 1)


async def test_missing_metric_means_nothing_is_covered(db_session: AsyncSession) -> None:
    """Нет хотя бы одной метрики — серия не собрана.

    Иначе `org_cost`, которого нет вовсе, никогда бы и не появился: инкремент
    считался бы от `org_traffic` и пропускал бы всю историю второй метрики.
    """
    project = await _project(db_session, "partial.example.com")
    db_session.add(
        MetricPoint(
            project_id=project.id,
            metric=Metric.ORG_TRAFFIC,
            point_date=date(2025, 5, 1),
            value=100.0,
            source=MetricSource.FIXTURE,
            fetched_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()

    known = await coverage(db_session, project.id, STAGE1_METRICS, MetricSource.FIXTURE)

    assert known.is_empty


async def test_source_separates_fixture_from_live(db_session: AsyncSession) -> None:
    """Синтетика не считается покрытием живых данных.

    Иначе переключение на живой ключ в Ф7 «увидело» бы историю собранной и не
    купило бы ничего — сервис молча показывал бы заказчику синтетику.
    """
    project = await _project(db_session, "src.example.com")
    for metric in STAGE1_METRICS:
        db_session.add(
            MetricPoint(
                project_id=project.id,
                metric=metric,
                point_date=date(2025, 5, 1),
                value=100.0,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()

    known = await coverage(db_session, project.id, STAGE1_METRICS, MetricSource.LIVE)

    assert known.is_empty
