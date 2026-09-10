"""Генератор синтетических серий: домен + сценарий + seed → история метрик.

Детерминирован полностью. Два вызова с одинаковыми аргументами дают одинаковые
числа (пример B7) — иначе golden-таблица Ф3 «серия → группа» перезаписывалась бы
при каждом прогоне и перестала бы что-либо удерживать.

Случайность здесь только для правдоподобия формы (шум ±3 %), и её зерно —
`sha256(домен, сценарий, seed)`, а не `hash()`: встроенный хеш строки
рандомизируется между процессами, и «детерминированный» генератор давал бы
разные серии в CI и локально.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date

from ahrefs_cases.collect.fixtures.scenarios import SHAPES, ScenarioName, ScenarioShape
from ahrefs_cases.storage._enums import Metric

_NOISE = 0.03
_SPIKE_FACTOR = 3.0
_TRAFFIC_RANGE = (800, 45_000)
_CPC_RANGE = (0.4, 2.5)
_KEYWORD_SHARES = {
    Metric.KW_TOP3: 0.004,
    Metric.KW_TOP4_10: 0.011,
    Metric.KW_TOP11_20: 0.019,
    Metric.KW_TOP21_50: 0.041,
    Metric.KW_TOP51_PLUS: 0.092,
}
_PAGES_PER_TRAFFIC = 0.02
_SEARCH_VOLUME_FACTOR = 7.5
_DR_RANGE = (28, 62)
_DR_GAIN = 9


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """Месяц и все метрики в нём. Провайдер отдаёт из него только запрошенные."""

    at: date
    values: dict[Metric, float]


def generate_series(
    domain: str,
    scenario: ScenarioName,
    *,
    seed: int,
    end: date,
) -> list[SeriesPoint]:
    """История по домену: помесячно, назад от `end`.

    `end` — конец периода работ проекта, а не «сегодня»: кейс не должен меняться
    от даты пересборки (см. докстринг `Project.period_end`).
    """
    shape = SHAPES[scenario]
    rng = _rng(domain, scenario, seed)
    base_traffic = rng.uniform(*_TRAFFIC_RANGE)
    cpc = rng.uniform(*_CPC_RANGE)
    base_refdomains = rng.uniform(40, 900)
    base_dr = rng.uniform(*_DR_RANGE)

    points: list[SeriesPoint] = []
    for index, at in enumerate(_months(end, shape.months)):
        if index in shape.holes:
            continue
        traffic = base_traffic * _traffic_factor(shape, index) * _noise(rng)
        refdomains = base_refdomains * _refdomains_factor(shape, index) * _noise(rng)
        progress = _progress(shape, index)
        points.append(
            SeriesPoint(
                at=at,
                values=_values(traffic, refdomains, cpc, base_dr + _DR_GAIN * progress),
            )
        )
    return points


def _values(traffic: float, refdomains: float, cpc: float, dr: float) -> dict[Metric, float]:
    """Все метрики одной точки. Считаются от трафика, потому что в реальности
    они и связаны: рост позиций без роста трафика — не кейс, а аномалия."""
    values: dict[Metric, float] = {
        Metric.ORG_TRAFFIC: float(round(traffic)),
        Metric.ORG_COST: round(traffic * cpc, 2),
        Metric.REFDOMAINS: float(round(refdomains)),
        Metric.DR: float(round(dr, 1)),
        Metric.PAGES: float(round(traffic * _PAGES_PER_TRAFFIC)),
        Metric.SEARCH_VOLUME: float(round(traffic * _SEARCH_VOLUME_FACTOR)),
    }
    values.update(
        {metric: float(round(traffic * share)) for metric, share in _KEYWORD_SHARES.items()}
    )
    return values


def _rng(domain: str, scenario: ScenarioName, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{domain}|{scenario.value}|{seed}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))  # noqa: S311 — не криптография, а форма данных


def _months(end: date, count: int) -> list[date]:
    """`count` первых чисел месяцев, заканчивая месяцем `end`."""
    months: list[date] = []
    year, month = end.year, end.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def _progress(shape: ScenarioShape, index: int) -> float:
    """Доля пройденного пути, 0 → 1. Один месяц истории — сразу конец пути."""
    if shape.months <= 1:
        return 1.0
    return index / (shape.months - 1)


def _traffic_factor(shape: ScenarioShape, index: int) -> float:
    factor = 1.0 + (shape.traffic_growth - 1.0) * _progress(shape, index)
    if shape.tail_months and index >= shape.months - shape.tail_months:
        factor *= shape.tail_factor
    return factor


def _refdomains_factor(shape: ScenarioShape, index: int) -> float:
    factor = 1.0 + (shape.refdomains_growth - 1.0) * _progress(shape, index)
    if shape.spike_month is not None and index >= shape.spike_month:
        factor *= _SPIKE_FACTOR
    return factor


def _noise(rng: random.Random) -> float:
    return 1.0 + rng.uniform(-_NOISE, _NOISE)
