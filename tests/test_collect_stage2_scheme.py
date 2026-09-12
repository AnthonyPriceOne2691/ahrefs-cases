"""Шаг 2: схема выбирается на каждый endpoint.

Примеры приёмки поставки `collect-stage2-scheme`: E1 (keywords точками), E2
(refdomains историей), E3 (два способа у одного проекта), E4 (перекрытие окон),
E5 (смета по тридцати кандидатам), E7 (разреженный шаг 2 не трогает правило
дыры), E8 (кэш по окнам).

Числа здесь не круглые и взяты не из головы: они считаются по замеренной
формуле `max(50, строки × (1 + сумма цен полей))`. Цены полей замерены живым
ключом 12.09.2026: трафик 10, ссылающиеся домены 5, страницы и каждый ключевой
бакет по 1.

**Числа этого файла переписаны 12.09.2026**, и не потому, что менялась логика:
прежняя модель считала любое поле по 10 и завышала цену позиций в семь раз. С
замеренными ценами решения о схеме изменились — это и проверяется ниже.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify import series as series_module
from ahrefs_cases.collect.endpoints import (
    KEYWORDS_HISTORY,
    PAGES_HISTORY,
    REFDOMAINS_HISTORY,
    TOTAL_SEARCH_VOLUME_HISTORY,
)
from ahrefs_cases.collect.plan import build_stage2_plan
from ahrefs_cases.collect.scheme import CollectScheme, PointWindows, choose_scheme
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
LONG_END = date(2026, 6, 30)
NOW = date(2026, 9, 15)
WINDOWS = PointWindows(point_months=2)


def _choose(spec, end: date, *, window: int = 2):
    return choose_scheme(
        period_start=START,
        period_end=end,
        spec=spec,
        windows=PointWindows(point_months=window),
        max_history_months=24,
        mode="auto",
    )


def test_keywords_scheme_follows_the_measured_price() -> None:
    """E1: у позиций пять полей, но каждое стоит единицу — строка 6, не 51.

    Прежняя модель («10 за любое поле») делала историю позиций дороже точек в
    четыре с половиной раза, и схема выбиралась ради экономии в 714 units.
    Замер 12.09.2026 оставил от этой экономии **восемь units** на проект:
    точки всё ещё дешевле, но разница перестала быть доводом.
    """
    choice = _choose(KEYWORDS_HISTORY, date(2026, 6, 1))

    assert KEYWORDS_HISTORY.row_units() == 6, "1 за строку + пять бакетов по 1"
    assert choice.scheme is CollectScheme.TWO_POINTS
    assert choice.units_two_points == 100
    assert choice.units_full_history == 108
    assert "8 units" in choice.reason, "экономия названа числом — и она копеечная"


def test_cheap_endpoint_goes_by_history() -> None:
    """E2: обратный случай к E1 на **том же периоде** — страницы стоят 2 за строку.

    Пример пришлось сменить: после замера у ссылающихся доменов и позиций цена
    строки совпала (по 6), и они перестали расходиться в схеме. Правило от
    этого не изменилось — схема выбирается на endpoint по его цене, — но
    показывать его надо на паре, которая различается **сейчас**, а не была
    различной когда-то (урок L48).
    """
    choice = _choose(PAGES_HISTORY, date(2026, 6, 1))

    assert PAGES_HISTORY.row_units() == 2
    assert choice.scheme is CollectScheme.FULL_HISTORY
    assert choice.units_full_history == 50, "18 строк по 2 не пробивают минимум"
    assert choice.units_two_points == 100


def test_refdomains_window_overlap_is_named() -> None:
    """E4: под минимум у refdomains влезает десять строк, и на коротком периоде
    окна точек перекрылись бы — в объяснении это названо."""
    choice = _choose(REFDOMAINS_HISTORY, date(2025, 6, 1))

    assert REFDOMAINS_HISTORY.rows_under_minimum() == 8
    assert choice.scheme is CollectScheme.FULL_HISTORY
    assert "перекрыл" in choice.reason


def test_long_period_flips_refdomains_to_points() -> None:
    """E9: у refdomains граница тоже есть, просто дальше — с двадцати одной строки.

    **Пример добавлен при реализации.** Спека говорила «refdomains собирается
    историей», и это неправда в общем виде: правило одно для всех endpoint'ов,
    просто точка перелома у каждого своя. Записать «refdomains — всегда
    история» значило бы захардкодить сегодняшний период.
    """
    short = _choose(REFDOMAINS_HISTORY, date(2025, 6, 1))
    long = _choose(REFDOMAINS_HISTORY, date(2026, 6, 1))

    assert short.scheme is CollectScheme.FULL_HISTORY, "E9: 6 строк — история"
    assert long.scheme is CollectScheme.TWO_POINTS, "E9: 18 строк — точки"
    assert long.units_full_history > long.units_two_points


async def _project(session: AsyncSession, domain: str, end: date = LONG_END) -> Project:
    row = f"{domain},{START.isoformat()},{end.isoformat()},fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (await session.execute(select(Project).where(Project.domain == domain))).scalars().one()


async def test_schemes_are_counted_per_endpoint(db_session: AsyncSession) -> None:
    """E3: схема выбирается на **пару** «проект + endpoint», и так же считается.

    Раньше пример показывал расхождение схем у одного проекта; после замера
    цены у обоих endpoint'ов шага 2 совпали, и расхождения больше нет. Само
    правило от этого не изменилось, и проверять надо его: отчёт считает
    **проекты** по каждому endpoint'у, а не задачи — у пары их может быть две,
    и счёт по задачам дал бы число, которого нет ни у кого на экране (L13).
    """
    project = await _project(db_session, "mixed.example.com")

    plan = await build_stage2_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )
    breakdown = plan.scheme_breakdown()

    schemes = {endpoint: choice.scheme for (_pid, endpoint), choice in plan.choices.items()}
    assert schemes["keywords-history"] is CollectScheme.TWO_POINTS
    assert schemes["refdomains-history"] is CollectScheme.TWO_POINTS
    assert breakdown.projects(CollectScheme.TWO_POINTS) == 2, "по проекту на каждый endpoint"
    assert len(plan.tasks) == 4, "по две точки на каждый из двух endpoint'ов"
    lines = "\n".join(breakdown.as_lines())
    assert "keywords-history two_points: 1 проект(ов)" in lines
    assert "refdomains-history two_points: 1 проект(ов)" in lines


async def test_estimate_for_thirty_candidates(db_session: AsyncSession) -> None:
    """E5: тридцать кандидатов стоят 6 000 units вместо 6 480.

    Число приёмки переписано 12.09.2026: по замеренным ценам шаг 2 подешевел
    втрое (было 8 820), а вместе с ним растаяла и сама экономия схемы — 480
    units на тридцати проектах против прежних 21 420. Шаг 2 перестал быть
    самой дорогой частью прогона.
    """
    projects = [await _project(db_session, f"c{index}.example.com") for index in range(30)]

    plan = await build_stage2_plan(
        db_session, projects, source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )
    breakdown = plan.scheme_breakdown()

    assert plan.estimated_units() == 6_000
    assert breakdown.units_if_history == 6_480
    assert breakdown.units_if_auto == 6_000
    assert "экономия 480" in "\n".join(breakdown.as_lines())


async def test_sparse_stage2_does_not_trip_the_series_gap_rule(db_session: AsyncSession) -> None:
    """E7: разреженный шаг 2 не делает серию недостоверной.

    Правило `max_series_gap_months` считается по `org_traffic`, то есть по шагу
    1, — и это единственная причина, по которой точки на шаге 2 вообще
    допустимы (Z6 сюда не дотягивается). Проверяется расчётом по серии, а не
    рассуждением: если однажды правило начнёт смотреть на все метрики, тест
    покраснеет, и это будет ровно то место, где нужно остановиться.
    """
    project = await _project(db_session, "sparse.example.com")
    for month in range(1, 13):  # трафик плотный, шаг 1 собран историей
        db_session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=1000.0 + month,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    for month in (1, 2, 11, 12):  # ключи — двумя точками, между ними дыра
        db_session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.KW_TOP3,
                point_date=date(2025, month, 1),
                value=10.0 + month,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()

    series = await series_module.load_series(db_session, project.id, MetricSource.FIXTURE)
    traffic_gap = series_module.max_gap_months(
        series_module.months_covered(series, Metric.ORG_TRAFFIC)
    )
    keywords_gap = series_module.max_gap_months(
        series_module.months_covered(series, Metric.KW_TOP3)
    )

    assert traffic_gap == 0, "серия трафика плотная — по ней и судит правило"
    assert keywords_gap == 8, "у ключей дыра восемь месяцев, и она намеренная"


async def test_bought_window_is_not_bought_twice_on_stage2(db_session: AsyncSession) -> None:
    """E8: кэш по окнам действует и на шаге 2."""
    project = await _project(db_session, "cached2.example.com")
    first = await build_stage2_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )
    keywords_tasks = [task for task in first.tasks if task.spec is KEYWORDS_HISTORY]
    window = keywords_tasks[0].request
    # Окно точки шире двух месяцев: у дешёвой строки под минимум влезает
    # восемь, и планировщик берёт их даром. Засеиваем окно целиком — иначе
    # кэш честно скажет «куплено не всё» (и будет прав).
    window_months = range(window.date_from.month, window.date_to.month + 1)
    for metric in KEYWORDS_HISTORY.metrics.values():
        for month in window_months:
            db_session.add(
                MetricPoint(
                    project_id=project.id,
                    metric=metric,
                    point_date=date(window.date_from.year, month, 1),
                    value=5.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
                )
            )
    await db_session.flush()

    second = await build_stage2_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=WINDOWS
    )

    assert len(keywords_tasks) == 2
    assert len([task for task in second.tasks if task.spec is KEYWORDS_HISTORY]) == 1
    assert any("уже куплено" in item.reason for item in second.cached)


@pytest.mark.parametrize(
    ("spec", "expected_free_rows"),
    [(TOTAL_SEARCH_VOLUME_HISTORY, 4), (PAGES_HISTORY, 25)],
)
def test_free_rows_follow_the_price_not_the_endpoint(spec, expected_free_rows: int) -> None:
    """Сколько строк бесплатны под минимумом — следствие цены, а не имени.

    У дорогой строки впрок не купишь: объём поиска стоит 11 за строку, и под
    минимум влезают четыре. У страниц строка стоит 2 — и бесплатных строк
    двадцать пять. Это не выбор, а арифметика от замеренной цены.
    """
    assert spec.rows_under_minimum() == expected_free_rows, "E4: ёмкость минимума — следствие цены"
