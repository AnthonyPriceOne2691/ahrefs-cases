"""Ступень кейса: докупка под графики и числа.

Примеры приёмки поставки `collect-case-step`: E1 (докупается середина), E2
(узкий набор полей), E3 (распределение на границах), E4 (traffic value точками),
E5 (только good и medium), E6 (watermark не обманывает), E7 (повтор ничего не
докупает), E8 (смета на десяти кейсах), E9 (агрегация по типу метрики).

Числа считаются по замеренной формуле: цена строки `10 × поля + 1`. У кривой
позиций два поля — 21, у полного распределения пять — 51.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.series import FLOW_METRICS, aggregate
from ahrefs_cases.collect.cache import missing_span
from ahrefs_cases.collect.endpoints import (
    DOMAIN_RATING_HISTORY,
    KEYWORDS_GRAPH,
    KEYWORDS_HISTORY,
    METRICS_VALUE,
    STAGE3_SPECS,
)
from ahrefs_cases.collect.plan import build_case_plan
from ahrefs_cases.collect.scheme import CollectScheme, PointWindows
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
START = date(2025, 1, 1)
END = date(2026, 6, 30)
NOW = date(2026, 9, 15)
WINDOWS = PointWindows(point_months=2)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Планирование ступени не ходит в сеть: план считается до запросов."""

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "планирование ступени кейса не ходит в сеть"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


async def _project(session: AsyncSession, domain: str) -> Project:
    row = f"{domain},{START.isoformat()},{END.isoformat()},fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (
        (await session.execute(select(Project).where(Project.domain == domain))).scalars().one()
    )


async def _stage2_points(session: AsyncSession, project: Project) -> None:
    """То, что оставил шаг 2: все пять корзин, но только на границах периода."""
    boundaries = [date(2025, 1, 1), date(2025, 2, 1), date(2026, 5, 1), date(2026, 6, 1)]
    for metric in KEYWORDS_HISTORY.metrics.values():
        for month in boundaries:
            session.add(
                MetricPoint(
                    project_id=project.id,
                    metric=metric,
                    point_date=month,
                    value=10.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
                )
            )
    await session.flush()


def test_curve_costs_less_because_it_asks_for_fewer_fields() -> None:
    """E2: та же ручка, другой `select` — цена строки падает с 51 до 21.

    Рычаг, которым не пользовались ни разу: цена строки это `10 × поля + 1`.
    Графику нужны топ-3 и топ-10, остальные три корзины живут в кейсе числами
    на границах периода.
    """
    assert KEYWORDS_GRAPH.path == KEYWORDS_HISTORY.path, "ручка та же"
    assert KEYWORDS_GRAPH.select == ("date", "top3", "top4_10")
    assert KEYWORDS_GRAPH.row_units() == 21
    assert KEYWORDS_HISTORY.row_units() == 51
    assert KEYWORDS_GRAPH.estimate_units(15) == 315
    assert KEYWORDS_HISTORY.estimate_units(15) == 765


def test_curve_is_bought_as_series_even_though_points_are_cheaper() -> None:
    """Назначение бьёт цену: кривая покупается серией, хотя точки дешевле.

    Две точки обошлись бы в 100 units против 399 за серию — но показать по ним
    нечего. Цена решает только там, где назначение допускает оба варианта.
    """
    assert KEYWORDS_GRAPH.needs_series is True
    assert METRICS_VALUE.needs_series is False
    assert 2 * KEYWORDS_GRAPH.estimate_units(2) < KEYWORDS_GRAPH.estimate_units(19)


async def test_only_the_missing_middle_is_bought(db_session: AsyncSession) -> None:
    """E1 и E6: докупается середина, и watermark этому не мешает.

    После шага 2 у позиций есть первые и последние месяцы периода. `coverage`
    вернул бы watermark по последнему месяцу, `next_date_from` сказал бы
    «докупать нечего», и кривая осталась бы из двух точек — молча (урок L27).
    """
    project = await _project(db_session, "curve.example.com")
    await _stage2_points(db_session, project)

    span = await missing_span(
        db_session,
        project.id,
        tuple(KEYWORDS_GRAPH.metrics.values()),
        MetricSource.FIXTURE,
        window_from=START,
        window_to=date(2026, 6, 1),
    )
    plan = await build_case_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    assert span == (date(2025, 3, 1), date(2026, 4, 1)), "середина между купленными границами"
    curve = [task for task in plan.tasks if task.spec is KEYWORDS_GRAPH]
    assert len(curve) == 1
    assert curve[0].expected_rows() == 14
    assert curve[0].estimated_units() == 294, "14 строк по 21 — платим только за дыру"


async def test_traffic_value_is_bought_as_two_points(db_session: AsyncSession) -> None:
    """E4: стоимость трафика в кейсе — число, а не кривая."""
    project = await _project(db_session, "value.example.com")

    plan = await build_case_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    value_tasks = [task for task in plan.tasks if task.spec is METRICS_VALUE]
    choice = plan.choices[(project.id, METRICS_VALUE.name)]
    assert choice.scheme is CollectScheme.TWO_POINTS
    assert len(value_tasks) == 2
    assert sum(task.estimated_units() for task in value_tasks) == 100


async def test_distribution_at_the_boundaries_stays_complete(db_session: AsyncSession) -> None:
    """E3: середина не обязана знать все пять корзин — границы их уже знают.

    Кейс показывает распределение топ-3 / топ-10 / топ-100 числами на границах
    периода; между ними идёт кривая по двум корзинам. Никакого выдуманного
    значения при этом не появляется.
    """
    project = await _project(db_session, "dist.example.com")
    await _stage2_points(db_session, project)

    stmt = select(MetricPoint.metric, MetricPoint.point_date).where(
        MetricPoint.project_id == project.id
    )
    rows = (await db_session.execute(stmt)).all()

    at_start = {row.metric for row in rows if row.point_date == date(2025, 1, 1)}
    assert at_start == set(KEYWORDS_HISTORY.metrics.values()), "на границе все пять корзин"
    assert set(KEYWORDS_GRAPH.metrics.values()) < at_start, "кривая берёт подмножество"


async def test_second_run_buys_nothing(db_session: AsyncSession) -> None:
    """E7: серия куплена целиком — ступень молчит и не тратит ни unit."""
    project = await _project(db_session, "again.example.com")
    for metric in KEYWORDS_GRAPH.metrics.values():
        for index in range(18):
            month = date(2025 + index // 12, index % 12 + 1, 1)
            db_session.add(
                MetricPoint(
                    project_id=project.id,
                    metric=metric,
                    point_date=month,
                    value=5.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
                )
            )
    await db_session.flush()

    plan = await build_case_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    curve = [task for task in plan.tasks if task.spec is KEYWORDS_GRAPH]
    assert curve == []
    assert any("уже куплена целиком" in item.reason for item in plan.cached)


async def test_estimate_for_ten_cases(db_session: AsyncSession) -> None:
    """E8: десять кейсов стоят 4 940 units.

    Вся экономия поставки — в составе полей и в том, что платим только за дыру:
    докупка позиций в лоб (пять корзин, весь период) стоила бы 969 на кейс,
    то есть почти столько же, сколько вся ступень на десяти.
    """
    projects = []
    for index in range(10):
        project = await _project(db_session, f"case{index}.example.com")
        await _stage2_points(db_session, project)
        projects.append(project)

    plan = await build_case_plan(
        db_session, projects, source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    assert plan.estimated_units() == 4_940
    assert len(STAGE3_SPECS) == 3, "кривая позиций, стоимость трафика и DR"
    per_case = plan.estimated_units() / len(projects)
    assert per_case == 494, "294 за дыру в кривой, 100 за стоимость трафика, 100 за DR"


async def test_dr_is_bought_as_a_number_for_cases(db_session: AsyncSession) -> None:
    """E10: DR — must-have по ТЗ, и в кейсе это число.

    Он стоял под флагом на шаге 2 и был выключен: тридцати кандидатам историей
    обошёлся бы в 3000 units. Ступень покупает его двумя точками десяти
    проектам — 1000. Требование ТЗ выполняется, а не откладывается флагом
    (урок L33).
    """
    project = await _project(db_session, "dr.example.com")

    plan = await build_case_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    choice = plan.choices[(project.id, DOMAIN_RATING_HISTORY.name)]
    tasks = [task for task in plan.tasks if task.spec is DOMAIN_RATING_HISTORY]
    assert choice.scheme is CollectScheme.TWO_POINTS, "в кейсе DR это «было → стало»"
    assert sum(task.estimated_units() for task in tasks) == 100
    assert choice.units_full_history == 198, "историей стоил бы вдвое дороже: 18 строк по 11"


@pytest.mark.parametrize(
    ("metric", "flow", "expected"),
    [
        (Metric.ORG_TRAFFIC, True, 3300.0),
        (Metric.REFDOMAINS, False, 120.0),
    ],
)
def test_quarter_aggregation_depends_on_metric_kind(
    metric: Metric, flow: bool, expected: float
) -> None:
    """E9: поток суммируется, запас берётся на конец квартала.

    Одно правило на обе группы врёт в одну сторону всегда: сложить три месяца
    ссылающихся доменов значит показать втрое больше, чем есть, а взять
    последний месяц трафика — треть визитов за квартал.
    """
    months = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)]
    by_month = dict(zip(months, [1000.0, 1100.0, 1200.0] if flow else [100.0, 110.0, 120.0]))

    assert (metric in FLOW_METRICS) is flow
    assert aggregate(by_month, months, flow=flow) == expected


def test_missing_month_is_not_a_zero_in_aggregation() -> None:
    """Отсутствующий месяц не обнуляет квартал и не считается нулём.

    То же правило, что в `points._average`: «данных нет» и «ноль визитов» —
    разные утверждения, и квартал без данных обязан быть `None`, а не нулём.
    """
    months = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)]

    assert aggregate({date(2025, 2, 1): 500.0}, months, flow=True) == 500.0
    assert aggregate({}, months, flow=True) is None
