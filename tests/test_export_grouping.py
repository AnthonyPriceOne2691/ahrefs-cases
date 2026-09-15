"""Свёртка месяцев в кварталы и годы. Примеры приёмки E2–E5.

Главное здесь — не арифметика, а то, что **правило зависит от природы метрики**.
Сложить ссылающиеся домены за три месяца значит показать втрое больше доменов,
чем их есть; взять трафик за последний месяц квартала — показать треть.
"""

from __future__ import annotations

from datetime import date

import pytest

from ahrefs_cases.cases.model import CaseSeries
from ahrefs_cases.classify.points import KW_TOP10
from ahrefs_cases.export.charts import curve_blocks
from ahrefs_cases.export.grouping import Grouping, period_start, regroup, regroup_window
from ahrefs_cases.storage._enums import Metric

MONTHS_2025 = [date(2025, month, 1) for month in range(1, 13)]


def _series(subject: str, values: list[float], months: list[date] | None = None) -> CaseSeries:
    return CaseSeries(
        subject=subject, points=tuple(zip(months or MONTHS_2025, values, strict=True))
    )


def test_month_grouping_changes_nothing() -> None:
    """E1: помесячный шаг возвращает ряды как есть — сегодняшний рисунок."""
    item = _series(Metric.ORG_TRAFFIC.value, [float(index) for index in range(12)])

    assert regroup([item], Grouping.MONTH) == (item,)


def test_flow_is_averaged_over_the_quarter() -> None:
    """E2: трафик — поток: квартал это СРЕДНИЙ месяц, а не сумма трёх.

    До 15.09.2026 здесь была сумма, и на ровных данных она выглядела разумно.
    Правило сменил не вкус, а неполные корзины — см. `test_partial_buckets…`.
    """
    item = _series(Metric.ORG_TRAFFIC.value, [100.0] * 12)

    folded = regroup([item], Grouping.QUARTER)[0]

    assert folded.points == (
        (date(2025, 1, 1), 100.0),
        (date(2025, 4, 1), 100.0),
        (date(2025, 7, 1), 100.0),
        (date(2025, 10, 1), 100.0),
    )


@pytest.mark.parametrize("subject", [Metric.REFDOMAINS.value, Metric.KW_TOP3.value, KW_TOP10])
def test_stock_is_taken_at_the_end_of_the_quarter(subject: str) -> None:
    """E3: запас — состояние на момент: квартал это значение на конец.

    Производный «топ-10» проверяется наравне: его нет в перечислении метрик, и
    неизвестная подпись обязана считаться запасом, а не потоком.
    """
    item = _series(subject, [float(index) for index in range(1, 13)])

    folded = regroup([item], Grouping.QUARTER)[0]

    assert folded.points == (
        (date(2025, 1, 1), 3.0),
        (date(2025, 4, 1), 6.0),
        (date(2025, 7, 1), 9.0),
        (date(2025, 10, 1), 12.0),
    )


def test_year_folds_twelve_months_by_the_same_rule() -> None:
    """E4: год — тот же выбор правила, только период длиннее."""
    flow = _series(Metric.ORG_TRAFFIC.value, [10.0] * 12)
    stock = _series(Metric.REFDOMAINS.value, [float(index) for index in range(1, 13)])

    folded = {item.subject: item.points for item in regroup([flow, stock], Grouping.YEAR)}

    assert folded[Metric.ORG_TRAFFIC.value] == ((date(2025, 1, 1), 10.0),)
    assert folded[Metric.REFDOMAINS.value] == ((date(2025, 1, 1), 12.0),)


def test_incomplete_period_folds_by_what_exists() -> None:
    """E5: неполный квартал сворачивается по тем месяцам, что измерены.

    Делитель — число ИЗМЕРЕННЫХ месяцев: делить на три там, где куплено два,
    значило бы засчитать неизмеренный месяц за ноль — то же самое, что
    дорисовать провал (то же правило, что в `points._average`).
    """
    months = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 4, 1)]
    item = _series(Metric.ORG_TRAFFIC.value, [100.0, 100.0, 50.0], months)

    folded = regroup([item], Grouping.QUARTER)[0]

    assert folded.points == ((date(2025, 1, 1), 100.0), (date(2025, 4, 1), 50.0))


def test_partial_buckets_do_not_invent_growth() -> None:
    """Корзины разной полноты сопоставимы между собой.

    Это и есть причина, по которой правило сменилось. Период работ почти
    никогда не ложится на календарные кварталы: у проекта 12.24 → 12.25 в
    корзине 2024 года один месяц, в корзине 2025-го двенадцать. Суммой это
    рисовало прямую от одного месяца до двенадцати — кривая показывала не рост
    трафика, а разницу в числе месяцев, и владелец увидел это на живом проекте
    (78 531 за месяц, 228 855 за квартал, 755 835 за год на одних и тех же
    данных).

    Плоский ряд обязан оставаться плоским на любом шаге — иначе рисунок врёт.
    """
    months = [date(2024, 12, 1), *[date(2025, month, 1) for month in range(1, 13)]]
    item = _series(Metric.ORG_TRAFFIC.value, [100.0] * 13, months)

    yearly = regroup([item], Grouping.YEAR)[0]

    assert yearly.points == ((date(2024, 1, 1), 100.0), (date(2025, 1, 1), 100.0))


def test_empty_period_does_not_appear() -> None:
    """Квартала без единого измерения на рисунке нет вовсе."""
    months = [date(2025, 1, 1), date(2025, 9, 1)]
    item = _series(Metric.REFDOMAINS.value, [10.0, 20.0], months)

    folded = regroup([item], Grouping.QUARTER)[0]

    assert [anchor for anchor, _ in folded.points] == [date(2025, 1, 1), date(2025, 7, 1)]


def test_window_moves_to_the_same_coordinates() -> None:
    """E7: окно вердикта задано месяцами, а ось — периодами.

    Оставить окно в месяцах значит убрать полосу с рисунка: ни один её месяц не
    совпадёт с началом периода.
    """
    window = [date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1)]

    assert regroup_window(window, Grouping.QUARTER) == [date(2025, 1, 1), date(2025, 4, 1)]
    assert regroup_window(window, Grouping.YEAR) == [date(2025, 1, 1)]


def test_start_of_works_lands_on_the_axis_of_every_step() -> None:
    """Метка «старт работ» сворачивается тем же правилом, что и ось.

    Ось после свёртки состоит из НАЧАЛ периодов, а дата старта приходила
    месяцем. На квартальном и годовом шаге пунктир и надпись вставали не туда и
    переезжали при каждом переключении: владелец увидел старт у левого края на
    помесячном шаге и у правого — на годовом, на одном и том же проекте
    (15.09.2026).

    Проверяется через `curve_blocks`, а не через `curves_svg`: свёртка живёт в
    сборке блоков, и именно её результат уходит и в PDF, и в карточку.
    """
    months = [date(2024, 12, 1), *[date(2025, month, 1) for month in range(1, 13)]]
    item = _series(Metric.ORG_TRAFFIC.value, [100.0] * 13, months)
    start = date(2024, 12, 1)

    # Первая точка оси на каждом шаге: с ней метка старта обязана совпасть.
    for grouping, expected in (
        (Grouping.MONTH, date(2024, 12, 1)),
        (Grouping.QUARTER, date(2024, 10, 1)),
        (Grouping.YEAR, date(2024, 1, 1)),
    ):
        assert period_start(start, grouping) == expected

        blocks = curve_blocks([item], period_start=start, grouping=grouping)
        svg = blocks[0]["svg"]
        axis = regroup([item], grouping)[0].points

        # Старт попал в ПЕРВУЮ корзину оси, значит приглушать нечего: месяцев
        # до старта на этом рисунке нет вовсе.
        assert axis[0][0] == expected
        assert "старт работ" in svg
        assert 'opacity="0.04"' not in svg, (
            f"на шаге {grouping} приглушены месяцы до старта, хотя старт — первая точка оси: "
            "значит метка считается по несвёрнутой дате"
        )
