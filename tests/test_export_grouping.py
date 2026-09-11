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
from ahrefs_cases.export.grouping import Grouping, regroup, regroup_window
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


def test_flow_is_summed_over_the_quarter() -> None:
    """E2: трафик — поток: квартал это сумма трёх месяцев."""
    item = _series(Metric.ORG_TRAFFIC.value, [100.0] * 12)

    folded = regroup([item], Grouping.QUARTER)[0]

    assert folded.points == (
        (date(2025, 1, 1), 300.0),
        (date(2025, 4, 1), 300.0),
        (date(2025, 7, 1), 300.0),
        (date(2025, 10, 1), 300.0),
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

    assert folded[Metric.ORG_TRAFFIC.value] == ((date(2025, 1, 1), 120.0),)
    assert folded[Metric.REFDOMAINS.value] == ((date(2025, 1, 1), 12.0),)


def test_incomplete_period_folds_by_what_exists() -> None:
    """E5: неполный квартал сворачивается по тем месяцам, что измерены.

    Дорисовать недостающие нулями значило бы показать провал в месяце, которого
    мы не мерили (то же правило, что в `points._average`).
    """
    months = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 4, 1)]
    item = _series(Metric.ORG_TRAFFIC.value, [100.0, 100.0, 50.0], months)

    folded = regroup([item], Grouping.QUARTER)[0]

    assert folded.points == ((date(2025, 1, 1), 200.0), (date(2025, 4, 1), 50.0))


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
