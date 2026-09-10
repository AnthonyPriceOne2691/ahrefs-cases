"""Дельты между точками А и Б: абсолютная и относительная одновременно.

Обе сразу, потому что ТЗ требует обе: порог «хороших» комбинированный (≥ +50 %
И ≥ +1000 визитов), а сортировка внутри группы — по абсолютному приросту.
Одна относительная дала бы кейс «+400 %» на сайте с сорока визитами.
"""

from __future__ import annotations

from dataclasses import dataclass

from ahrefs_cases.classify.points import KW_TOP10, Point
from ahrefs_cases.storage._enums import Metric

_HUNDRED = 100.0


@dataclass(frozen=True, slots=True)
class Delta:
    """Изменение одной метрики. `pct is None` — рост от нуля."""

    before: float
    after: float
    absolute: float
    pct: float | None

    @property
    def grew(self) -> bool:
        return self.absolute > 0


def _delta(before: float, after: float) -> Delta:
    """Относительная дельта от нулевой базы не определена.

    `None`, а не бесконечность и не 100 %: рост с нуля до сорока визитов
    формально бесконечен, а по сути ничего не значит. Правила обязаны решать
    такой случай явно, поэтому им передаётся отсутствие числа, а не число.
    """
    absolute = after - before
    pct = (absolute / before) * _HUNDRED if before > 0 else None
    return Delta(before=before, after=after, absolute=absolute, pct=pct)


@dataclass(frozen=True, slots=True)
class Deltas:
    """Все дельты проекта, включая производную «топ-10»."""

    by_metric: dict[Metric, Delta]
    derived: dict[str, Delta]

    def metric(self, metric: Metric) -> Delta | None:
        return self.by_metric.get(metric)

    def top10(self) -> Delta | None:
        return self.derived.get(KW_TOP10)


def between(point_a: Point, point_b: Point) -> Deltas:
    """Дельты по метрикам, которые есть в **обеих** точках.

    Метрика, появившаяся только в конце периода, дельты не имеет: сравнивать
    её не с чем, и подставлять ноль значило бы объявить рост там, где просто
    не было измерений.
    """
    by_metric = {
        metric: _delta(before, point_b.values[metric])
        for metric, before in point_a.values.items()
        if metric in point_b.values
    }
    derived = {
        name: _delta(before, point_b.derived[name])
        for name, before in point_a.derived.items()
        if name in point_b.derived
    }
    return Deltas(by_metric=by_metric, derived=derived)
