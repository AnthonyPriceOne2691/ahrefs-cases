"""Серии метрик из базы — чтение без решений.

Единственное место, где классификация трогает базу на входе. Дальше всё
считают чистые функции: golden-таблица «сценарий → группа» обязана проверяться
без базы, иначе она станет медленной и начнёт зависеть от того, что лежит в
дев-окружении (урок L8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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


def aggregate(
    by_month: Mapping[date, float],
    months: Sequence[date],
    *,
    flow: bool,
) -> float | None:
    """Свернуть месяцы в одно значение — для квартального и годового вида.

    **Правило зависит от природы метрики, и одно на обе группы врёт.**

    - *Поток* — органический трафик: визиты за месяц. Квартал это сумма трёх
      месяцев; взять последний значило бы показать треть.
    - *Запас* — ссылающиеся домены, ключи в топе: состояние на момент, а не за
      период. Квартал это значение на конец; сложить три месяца значило бы
      показать втрое больше доменов, чем есть, — и в PDF это заметят не сразу.

    Месяцев, которых нет, здесь нет и в ответе: отсутствующий месяц не равен
    нулю (то же правило, что в `points._average`). Пустой набор даёт `None`, а
    не ноль: «данных нет» и «ноль визитов» — разные утверждения.
    """
    present = [by_month[month] for month in months if month in by_month]
    if not present:
        return None
    return sum(present) if flow else present[-1]


FLOW_METRICS = frozenset({Metric.ORG_TRAFFIC, Metric.ORG_COST})
"""Метрики-потоки: значение накоплено **за** месяц.

Остальные — запасы: число ссылающихся доменов и ключей в топе измеряется на
момент. Список здесь, а не в месте отрисовки, потому что свойство принадлежит
метрике, а не графику: экран Ф6 и PDF Ф4 обязаны сворачивать одинаково."""


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
