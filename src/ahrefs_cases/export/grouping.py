"""Свёртка месяцев в кварталы и годы — перед рисованием, не после.

Тумблер «месяц/квартал/год» решён владельцем при выборе вида графиков: на
двухлетнем проекте помесячная кривая это 24 точки пилы, по которой тренд читается
хуже, чем по восьми кварталам. Свёртка при этом **бесплатна**: месяцы уже
собраны, Ahrefs не спрашивается.

**Правило зависит от природы метрики, и одно на обе группы врёт.** Поток
(органический трафик, стоимость трафика) — это то, что накоплено *за* месяц:
квартал — сумма трёх. Запас (ссылающиеся домены, ключи в топе) измеряется *на
момент*: квартал — значение на конец. Сложить запас за три месяца значит
показать втрое больше доменов, чем есть, и в PDF такое замечают не сразу.

Список потоков берётся из классификации (`series.FLOW_METRICS`), а не пишется
здесь заново: свойство принадлежит метрике, а не графику.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum

from ahrefs_cases.cases.model import CaseSeries
from ahrefs_cases.classify.series import FLOW_METRICS


class Grouping(StrEnum):
    """Шаг кривой. Больше трёх значений ТЗ не называет."""

    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


_FLOW_SUBJECTS = frozenset(metric.value for metric in FLOW_METRICS)
"""Подписи потоков строками: ряды кривых адресуются `subject`, и среди них есть
производный «топ-10», которого нет в перечислении метрик. Неизвестная подпись
считается запасом — это верно для всех сегодняшних производных."""


def period_start(month: date, grouping: Grouping) -> date:
    """Начало периода, в который попадает месяц.

    Начало, а не конец: подпись оси рисуется по этой дате, и «01.25» у первого
    квартала читается как «с января», тогда как «03.25» выглядело бы как март.
    """
    if grouping is Grouping.YEAR:
        return date(month.year, 1, 1)
    if grouping is Grouping.QUARTER:
        return date(month.year, month.month - (month.month - 1) % 3, 1)
    return date(month.year, month.month, 1)


def regroup(series: Sequence[CaseSeries], grouping: Grouping) -> tuple[CaseSeries, ...]:
    """Свернуть ряды к выбранному шагу. Помесячный шаг возвращает их как есть."""
    if grouping is Grouping.MONTH:
        return tuple(series)
    return tuple(CaseSeries(subject=item.subject, points=_fold(item, grouping)) for item in series)


def _fold(item: CaseSeries, grouping: Grouping) -> tuple[tuple[date, float], ...]:
    """Точки одного ряда, свёрнутые по периодам.

    Период, в котором нет ни одного измеренного месяца, здесь не появляется
    вовсе: «данных нет» и «ноль» — разные утверждения, и дорисовать ноль значило
    бы показать провал в квартале, которого мы не мерили (урок L30).
    """
    flow = item.subject in _FLOW_SUBJECTS
    buckets: dict[date, list[float]] = {}
    for month, value in sorted(item.points):
        buckets.setdefault(period_start(month, grouping), []).append(value)
    return tuple(
        (anchor, sum(values) if flow else values[-1]) for anchor, values in sorted(buckets.items())
    )


def regroup_window(window: Sequence[date], grouping: Grouping) -> list[date]:
    """Окно точки А или Б в тех же координатах, что и кривая.

    Окно задано месяцами вердикта; после свёртки ось состоит из начал периодов,
    и полоса обязана лечь на те периоды, в которые эти месяцы попали — иначе
    она просто исчезнет с рисунка.
    """
    return sorted({period_start(month, grouping) for month in window})
