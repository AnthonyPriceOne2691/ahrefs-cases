"""Схема сбора: точки А/Б против истории целиком.

Примеры приёмки поставки `collect-scheme-stage1`: E1–E3 (выбор по цене), E4
(равенство), E5 (окно покупается до минимума), E6 (окно из порогов сдвигает
границу), E7 (перекрытие), E8 (запас до старта по потребности), E10 (смета
сходится с числом строк, которое реально пришло), E12 (кэш по окнам), E13
(глубина истории).

Выбор схемы — чистая функция, поэтому большая часть файла обходится без базы и
без провайдера: таблица периодов и ожидаемых решений читается как приложение к
спеке. Окна точек приходят параметром, а не из порогов заказчика, — тест не
имеет права стоять на файле, которого в репозитории нет (урок L21).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.plan import build_stage1_plan
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.collect.scheme import (
    CollectScheme,
    PointWindows,
    SchemeChoice,
    choose_scheme,
)
from ahrefs_cases.config.ahrefs import CollectSchemeMode
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
NOW = date(2026, 9, 15)


def _end_of(months: int) -> date:
    """Конец периода в `months` месячных строк, считая январь 2025 первой."""
    total = START.year * 12 + (START.month - 1) + months - 1
    return date(total // 12, total % 12 + 1, 1)


def _choose(
    *,
    months: int,
    window: int = 0,
    baseline: int = 0,
    mode: CollectSchemeMode = "auto",
    depth: int = 24,
) -> SchemeChoice:
    """Решение по проекту, чей период занимает `months` месячных строк."""
    return choose_scheme(
        period_start=START,
        period_end=_end_of(months),
        spec=METRICS_HISTORY,
        windows=PointWindows(point_months=window, baseline_months=baseline),
        max_history_months=depth,
        mode=mode,
    )


@pytest.mark.parametrize(
    ("months", "expected_rows", "scheme", "units_full", "units_points"),
    [
        # Строк в плане: у истории — весь период, у точек — два окна по четыре
        # месяца, сколько бы месяцев ни было между ними. Это и есть экономия.
        (4, 4, CollectScheme.FULL_HISTORY, 50, 100),
        (7, 7, CollectScheme.FULL_HISTORY, 77, 100),
        (9, 9, CollectScheme.FULL_HISTORY, 99, 100),
        (10, 8, CollectScheme.TWO_POINTS, 110, 100),
        (19, 8, CollectScheme.TWO_POINTS, 209, 100),
        (25, 8, CollectScheme.TWO_POINTS, 275, 100),
    ],
)
def test_scheme_is_chosen_by_price_and_counted_in_rows(
    months: int,
    expected_rows: int,
    scheme: CollectScheme,
    units_full: int,
    units_points: int,
) -> None:
    """E1–E3: граница между схемами проходит по **строкам**, а не по месяцам.

    Обе границы периода входят в ответ, поэтому проект «18 месяцев работ» — это
    19 строк. Из-за этой единицы точка безразличия стоит на девяти строках
    (99 против 100), а не на десяти: таблица в `docs/UNITS_OPTIMIZATION.md`
    считала строки равными месяцам и сдвигала границу на месяц — ровно там, где
    выбор и происходит.
    """
    choice = _choose(months=months)

    assert choice.scheme is scheme
    assert choice.units_full_history == units_full
    assert choice.units_two_points == units_points
    assert sum(window.rows for window in choice.windows) == expected_rows
    assert str(units_full) in choice.reason, "в объяснении обе цены, иначе смета необъяснима"
    assert str(units_points) in choice.reason


def test_equal_price_goes_to_history_because_graph_is_free() -> None:
    """E4: при равной цене — история целиком.

    Десять строк по 11 units — 110, две точки по окну 5 месяцев — тоже 110.
    Правило разрывает ничью в пользу истории, потому что она той же ценой даёт
    ещё и график, а проект, собранный точками, придётся докупать в Ф4.
    """
    choice = _choose(months=10, window=5)

    assert choice.units_full_history == choice.units_two_points == 110
    assert choice.scheme is CollectScheme.FULL_HISTORY
    assert "не дороже" in choice.reason


def test_point_window_is_bought_up_to_the_minimum() -> None:
    """E5: пороги просят два месяца — покупаем четыре, цена та же.

    Минимум 50 units за запрос — это ещё и неиспользованная ёмкость: при цене
    строки 11 под минимум влезает четыре строки (44), пятая его пробивает (55).
    Купленные впрок месяцы нужны калибровке Ф8: переход на медиану (M1) или
    расширение окна не потребует повторного платного прогона по сотне доменов.
    """
    asked_two = _choose(months=19, window=2)
    asked_four = _choose(months=19, window=4)

    point_a, point_b = asked_two.windows
    assert point_a.rows == 4, "окно запроса — четыре месяца, а не два"
    assert point_b.rows == 4
    assert asked_two.units_two_points == 100 == asked_four.units_two_points
    assert METRICS_HISTORY.estimate_units(4) == METRICS_HISTORY.estimate_units(1) == 50


def test_window_from_thresholds_moves_the_indifference_point() -> None:
    """E6: окно шире бесплатного максимума дорожает и сдвигает границу схем.

    Калибровка поднимает окно с 2 до 6 — точка начинает стоить 66, две точки
    132. Проект на 12 строк был «точками» (132 против 100), а стал «историей»
    (132 против 132 — ничья в пользу истории). Схема считается по действующей
    версии порогов; посчитанная по прежнему окну, она сделала бы смету ложной
    сразу после первой правки заказчика.
    """
    narrow = _choose(months=12, window=2)
    wide = _choose(months=12, window=6)

    assert narrow.scheme is CollectScheme.TWO_POINTS
    assert narrow.units_two_points == 100
    assert wide.units_two_points == 132
    assert wide.scheme is CollectScheme.FULL_HISTORY
    assert wide.windows[0].rows == 12


def test_overlapping_windows_are_named_in_the_reason() -> None:
    """E7: короткий период — история, и объяснение говорит про перекрытие.

    Отдельного правила «окна перекрылись» нет и быть не должно: правило цены
    само выбирает историю всюду, где окна перекрылись бы (доказательство — в
    докстринге `choose_scheme`). Но факт перекрытия остаётся в объяснении:
    оператору он показывает, почему точки для такого периода бессмысленны.
    """
    choice = _choose(months=6)

    assert choice.scheme is CollectScheme.FULL_HISTORY
    assert "перекрыл" in choice.reason


def test_months_before_start_are_bought_only_when_asked() -> None:
    """E8: запас до старта работ покупается по потребности, а не всегда.

    Было три месяца безусловно — 33 units на домен при цене строки 11, 3300 на
    сотне доменов. Читателя у них не было ни одного: точка А считается окном
    **вперёд** от старта работ, а расчёт baseline'а (`pre_start_baseline_months`)
    выключен и появится в Ф3б. Тот же класс, что Z4 в `docs/FINDINGS.md`.
    """
    without = _choose(months=19, baseline=0)
    with_baseline = _choose(months=19, baseline=3)

    assert without.windows[0].date_from == START
    assert with_baseline.windows[0].date_from == date(2024, 10, 1)
    assert with_baseline.units_full_history - without.units_full_history == 33


def test_history_depth_clamps_the_first_point() -> None:
    """E13: период глубже доступной истории — точка А берётся не от старта.

    Глубину задаёт тариф, и просить сорок месяцев значит получить меньше и не
    знать, что получил меньше. Ограничение сдвигает начало окна, а не молчит:
    в вердикте это видно справочной записью `history_truncated` (Z5).
    """
    choice = _choose(months=30, depth=24)
    point_a = choice.windows[0]

    assert point_a.date_from == date(2025, 6, 1), "глубже 24 месяцев от конца периода не просим"
    assert point_a.date_from > START, "точка А взята не от старта работ — это и есть усечение"
    assert point_a.rows == 4, "окно не съёжилось и не перевернулось: ширина сохранена"


def test_flag_off_keeps_history_but_still_prices_the_alternative() -> None:
    """E11: при `AHREFS_COLLECT_SCHEME=history` собираем историей и знаем цену точек.

    Флаг существует из-за Z6: проект, собранный точками, имеет дыру во всю
    середину периода, а правило достоверности серии считает такую дыру
    недостоверной серией. Пока классификация не различает дыру «не покупали» от
    дыры «у Ahrefs нет данных», включённая схема означала бы дешёвый сбор без
    кейсов. Цена альтернативы считается всё равно — иначе экономию нечем
    предъявить.
    """
    choice = _choose(months=19, mode="history")

    assert choice.scheme is CollectScheme.FULL_HISTORY
    assert choice.units == 209
    assert choice.units_two_points == 100
    assert choice.units_cheapest == 100
    assert "выключена флагом" in choice.reason


async def test_estimate_matches_the_rows_provider_returns() -> None:
    """E10: смета считает те же строки, которые действительно приходят.

    Ошибка на один месяц — это 11 units на домен и 1100 на сотне. Проверяется
    на обеих схемах: у окна точки и у истории разная арифметика границ, и
    сойтись должны обе.
    """
    provider = AhrefsFixture()
    for months in (7, 19):
        choice = _choose(months=months)
        for window in choice.windows:
            request = HistoryRequest(
                target="scheme.example.com",
                mode="subdomains",  # type: ignore[arg-type]
                country="US",
                date_from=window.date_from,
                date_to=window.date_to,
            )
            result = await provider.fetch_history(METRICS_HISTORY, request)
            assert len(result.points) == window.rows, f"{months} мес., окно {window.date_from}"
            assert result.units_actual == METRICS_HISTORY.estimate_units(window.rows)


async def _project(session: AsyncSession, domain: str, *, end: str = "2026-06-30") -> Project:
    row = f"{domain},2025-01-01,{end},fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (await session.execute(select(Project).where(Project.domain == domain))).scalars().one()


async def test_bought_window_is_not_bought_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E12: окно, купленное целиком, не покупается второй раз.

    Решение по окну бинарное, и это следствие цены: запрос на один месяц и на
    четыре стоят одинаково — 50 units. Сузить окно нельзя, поэтому оно либо
    куплено целиком, либо покупается целиком заново.

    Watermark из `coverage` здесь не годится принципиально: он хранит одну
    границу «собрано по такой-то месяц», и в схеме «две точки» граница от точки
    Б объявила бы купленным всё, что между точками, — окно точки А не купили бы
    никогда.
    """
    from ahrefs_cases import config

    monkeypatch.setattr(config.ahrefs, "collect_scheme", "auto")
    project = await _project(db_session, "cached-window.example.com")

    plan = await build_stage1_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=PointWindows()
    )
    assert len(plan.tasks) == 2, "две точки — два запроса"
    point_a = plan.tasks[0].request

    for shift in range(4):
        db_session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, 1 + shift, 1),
                value=100.0,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()

    second = await build_stage1_plan(
        db_session, [project], source=MetricSource.FIXTURE, now=NOW, windows=PointWindows()
    )

    assert point_a.date_from == date(2025, 1, 1)
    assert len(second.tasks) == 1, "окно точки А куплено — остаётся только точка Б"
    assert second.tasks[0].request.date_from > date(2025, 4, 1)
    assert [cached.reason for cached in second.cached] == ["окно 2025-01 уже куплено"]
    assert second.estimated_units() == 50


async def test_breakdown_counts_projects_not_tasks(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E9 (часть про отчёт): разбивка считает проекты, а не запросы.

    В схеме «две точки» у проекта два запроса одним endpoint'ом. Считать
    задачами — значит показать «проектов 3, собрано 6», то самое число, которое
    нельзя показывать человеку (урок L13, найден на шаге 2 воронки).
    """
    from ahrefs_cases import config

    monkeypatch.setattr(config.ahrefs, "collect_scheme", "auto")
    long_period = await _project(db_session, "long.example.com")
    short_period = await _project(db_session, "short.example.com", end="2025-05-31")

    plan = await build_stage1_plan(
        db_session,
        [long_period, short_period],
        source=MetricSource.FIXTURE,
        now=NOW,
        windows=PointWindows(),
    )
    breakdown = plan.scheme_breakdown()

    assert breakdown.projects(CollectScheme.TWO_POINTS) == 1
    assert breakdown.projects(CollectScheme.FULL_HISTORY) == 1
    assert len(plan.tasks) == 3, "две задачи у длинного проекта, одна у короткого"
    assert breakdown.units() == 155
    assert breakdown.units_if_history == 198 + 55
    assert breakdown.units_if_auto == 100 + 55
    assert "экономия 98" in "\n".join(breakdown.as_lines())
    assert all(
        share.endpoint == "metrics-history" for share in breakdown.shares
    ), "на шаге 1 endpoint один, и разрез по нему вырождается в прежний"
