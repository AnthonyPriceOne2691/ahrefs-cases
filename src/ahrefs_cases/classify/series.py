"""Серии метрик из базы — чтение без решений.

Единственное место, где классификация трогает базу на входе. Дальше всё
считают чистые функции: golden-таблица «сценарий → группа» обязана проверяться
без базы, иначе она станет медленной и начнёт зависеть от того, что лежит в
дев-окружении (урок L8).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint

MetricSeries = Mapping[Metric, Mapping[date, float]]
"""Метрика → (месяц → значение). Месяцев, которых нет, в словаре нет: дыра —
это отсутствие ключа, а не ноль. Различение заложено ещё генератором Ф2а и
здесь обязано сохраниться."""


async def load_series(session: AsyncSession, project_id: int, source: MetricSource) -> MetricSeries:
    """Все точки проекта одним запросом."""
    stmt = select(MetricPoint.metric, MetricPoint.point_date, MetricPoint.value).where(
        MetricPoint.project_id == project_id,
        MetricPoint.source == source,
    )
    series: dict[Metric, dict[date, float]] = {}
    for metric, point_date, value in (await session.execute(stmt)).all():
        series.setdefault(metric, {})[point_date] = float(value)
    return series


def months_covered(series: MetricSeries, metric: Metric) -> list[date]:
    """Отсортированные месяцы, по которым есть значения метрики."""
    return sorted(series.get(metric, {}))


def max_gap_months(months: list[date]) -> int:
    """Самая длинная дыра в серии, в месяцах.

    Считается по календарю, а не по числу пропущенных записей: между январём и
    апрелем пропущено два месяца, и именно это число сравнивается с порогом
    `max_series_gap_months`.
    """
    if len(months) < 2:
        return 0
    gaps = [_months_between(previous, current) - 1 for previous, current in pairwise(months)]
    return max(gaps) if gaps else 0


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)
