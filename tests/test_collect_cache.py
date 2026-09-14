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
    share_twin_points,
)
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.scheme import PointWindows
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

WINDOW_FROM = date(2024, 10, 1)
WINDOW_TO = date(2026, 8, 1)
NOW = date(2026, 9, 15)
STAGE1_METRICS = tuple(METRICS_HISTORY.metrics.values())
MULTI_METRICS = (Metric.ORG_TRAFFIC, Metric.ORG_COST)
"""Две метрики для правил, которые про **несколько** метрик в одном endpoint'е.

Шаг 1 просит одно поле с тех пор, как замер показал построчный биллинг:
`org_cost` удваивал цену строки и уехал в ступень графика Ф4. Правило «покрытие
— минимум по метрикам» от этого не исчезло: у `keywords-history` пять полей, и
проверять его надо на паре, а не на текущем составе шага 1."""

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
    """C3: TTL считается от `fetched_at`, а не от даты точки."""
    now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

    assert is_fresh(now - timedelta(hours=1), now) is True
    assert is_fresh(now - timedelta(days=3), now) is False
    assert is_fresh(None, now) is False


def test_window_from_wins_over_older_increment() -> None:
    """C2: инкремент не уводит запрос левее окна проекта.

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
    """C2: покрытие — минимум по метрикам, а не максимум.

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

    known = await coverage(db_session, project.id, MULTI_METRICS, MetricSource.FIXTURE)

    assert known.last_point == date(2025, 4, 1)


async def test_missing_metric_means_nothing_is_covered(db_session: AsyncSession) -> None:
    """C2: нет хотя бы одной метрики — серия не собрана.

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

    known = await coverage(db_session, project.id, MULTI_METRICS, MetricSource.FIXTURE)

    assert known.is_empty


async def test_source_separates_fixture_from_live(db_session: AsyncSession) -> None:
    """C2: синтетика не считается покрытием живых данных.

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


async def _campaign(session: AsyncSession, domain: str, period: tuple[str, str]) -> Project:
    """Кампания по домену: агентство ведёт один сайт несколькими периодами."""
    from sqlalchemy import select as _select

    start, end = period
    row = f"{domain},{start},{end},fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (
        (
            await session.execute(
                _select(Project).where(Project.period_start == date.fromisoformat(start))
            )
        )
        .scalars()
        .one()
    )


async def test_second_campaign_does_not_buy_the_same_months_again(
    db_session: AsyncSession,
) -> None:
    """Z8: общие месяцы двух кампаний одного домена не покупаются дважды.

    Агентство ведёт сайт двумя кампаниями, и это законно: проект опознаётся
    тройкой `(домен, режим, начало периода)`, кампании сравнивают между собой.
    Но ряды лежат с `project_id`, и кэш смотрел только на свой проект — вторая
    кампания платила за уже купленные месяцы по второму разу (209 units на
    историю по профилю ТЗ). Трафик домена за январь не зависит от того, в
    рамках какой кампании его спросили: месяц переносится, а не покупается.
    """
    first = await _campaign(db_session, "две-кампании.example", ("2025-01-01", "2025-12-01"))
    second = await _campaign(db_session, "две-кампании.example", ("2025-07-01", "2026-06-01"))
    for month in range(1, 13):
        db_session.add(
            MetricPoint(
                project_id=first.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=1000.0 + month,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()

    shared = await share_twin_points(
        db_session,
        [second],
        source=MetricSource.FIXTURE,
        windows=PointWindows(point_months=2),
    )
    await db_session.flush()
    known = await coverage(db_session, second.id, (Metric.ORG_TRAFFIC,), MetricSource.FIXTURE)

    assert shared > 0, "месяцы первой кампании не перенесены — вторая купит их заново"
    assert known.last_point == date(2025, 12, 1)
    # Докупать теперь надо только хвост, которого нет ни у одной кампании.
    assert next_date_from(
        known,
        window_from=date(2025, 7, 1),
        window_to=date(2026, 6, 1),
        now=NOW,
        fresh=True,
    ) == date(2026, 1, 1)


async def test_sharing_does_not_stretch_the_series_beyond_the_period(
    db_session: AsyncSession,
) -> None:
    """Перенос ограничен отрезком проекта — иначе он сам создаёт дыру.

    Кампания двухлетней давности растянула бы серию назад, между ней и нынешней
    зияла бы дыра в полтора года, и правило достоверности серии объявило бы
    «данных не хватает» там, где всё в порядке. Дефект был бы дороже
    исправляемого: тот стоил units, этот — кейсов.
    """
    old = await _campaign(db_session, "давняя-кампания.example", ("2023-01-01", "2023-06-01"))
    fresh = await _campaign(db_session, "давняя-кампания.example", ("2025-07-01", "2026-06-01"))
    for month in range(1, 7):
        db_session.add(
            MetricPoint(
                project_id=old.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2023, month, 1),
                value=500.0,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()

    shared = await share_twin_points(
        db_session,
        [fresh],
        source=MetricSource.FIXTURE,
        windows=PointWindows(point_months=2),
    )

    assert shared == 0, "перенесли месяцы, лежащие вне отрезка проекта"


async def test_sharing_ignores_another_target_mode(db_session: AsyncSession) -> None:
    """Домен тот же, режим другой — это другие числа, и переносить их нельзя.

    `subdomains` считает поддомены, `prefix` — только раздел: у проекта-раздела
    трафик меньше по построению. Перенос между режимами подменил бы данные
    молча, и подмену было бы видно только по величине.
    """
    from sqlalchemy import select as _select

    whole = await _campaign(db_session, "смена-режима.example", ("2025-01-01", "2025-12-01"))
    row = "смена-режима.example,2025-07-01,2026-06-01,fintech,US,seo,10,Acme,i.petrov,yes,prefix,"
    await accept(db_session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    section = (
        (await db_session.execute(_select(Project).where(Project.target_mode == "prefix")))
        .scalars()
        .one()
    )
    db_session.add(
        MetricPoint(
            project_id=whole.id,
            metric=Metric.ORG_TRAFFIC,
            point_date=date(2025, 8, 1),
            value=1000.0,
            source=MetricSource.FIXTURE,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()

    shared = await share_twin_points(
        db_session, [section], source=MetricSource.FIXTURE, windows=PointWindows(point_months=2)
    )

    assert shared == 0, "перенесли данные другого режима подсчёта"
