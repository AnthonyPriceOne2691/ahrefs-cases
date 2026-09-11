"""Точки А и Б: среднее по окну у границ периода работ.

Не первое и последнее значение серии. Одна аномальная точка на границе —
распродажа, сбой Ahrefs, выброс парсинга — иначе превращает шум в «рост», и
заказчику уходит PDF с результатом, которого не было (пример D1).

Окно берётся из порогов (`windows.point_a_months`), а не из константы: его
меняют вместе с калибровкой, и оно обязано попадать в версию порогов.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from ahrefs_cases.classify.series import MetricSeries
from ahrefs_cases.classify.thresholds import Windows
from ahrefs_cases.storage._enums import Metric

KW_TOP10 = "kw_top10"
"""Производная метрика «ключей в топ-10»: `top3 + top4_10`. В Ahrefs её нет —
она собирается из двух корзин, и делать это надо в одном месте, иначе
подтверждающее условие и объяснение к нему посчитают по-разному."""


@dataclass(frozen=True, slots=True)
class Point:
    """Значения метрик на границе периода и сколько месяцев в них усреднено."""

    at: date
    values: Mapping[Metric, float]
    derived: Mapping[str, float]
    months_used: int

    def get(self, metric: Metric) -> float | None:
        return self.values.get(metric)


def point_a(series: MetricSeries, period_start: date, windows: Windows) -> Point:
    """Точка А — среднее по первым месяцам периода работ, включая месяц старта."""
    months = _window_forward(period_start, windows.point_a_months)
    return _average(series, months, at=period_start)


def point_b(series: MetricSeries, period_end: date, windows: Windows) -> Point:
    """Точка Б — среднее по последним месяцам периода, включая месяц конца.

    Конец задаёт агентство, даже если работы продолжаются: иначе кейс менялся
    бы от даты пересборки (см. докстринг `Project.period_end`).
    """
    months = _window_backward(period_end, windows.point_b_months)
    return _average(series, months, at=period_end)


def _average(series: MetricSeries, months: list[date], *, at: date) -> Point:
    """Среднее по тем месяцам окна, которые в серии **есть**.

    Отсутствующий месяц не считается нулём: «данных нет» и «трафик упал в ноль»
    — разные вещи, и подмена первого вторым даёт готовый ложный кейс о падении.
    """
    values: dict[Metric, float] = {}
    used = 0
    for metric, by_month in series.items():
        present = [by_month[month] for month in months if month in by_month]
        if not present:
            continue
        values[metric] = sum(present) / len(present)
        used = max(used, len(present))

    derived: dict[str, float] = {}
    top3 = values.get(Metric.KW_TOP3)
    top4_10 = values.get(Metric.KW_TOP4_10)
    if top3 is not None or top4_10 is not None:
        derived[KW_TOP10] = (top3 or 0.0) + (top4_10 or 0.0)

    return Point(at=at, values=values, derived=derived, months_used=used)


def window_a(period_start: date, windows: Windows) -> list[date]:
    """Месяцы, по которым считается точка А.

    Публичные, потому что их надо не только считать, но и спрашивать: куплены
    ли эти месяцы под ту версию порогов, по которой пересчитывают (Ф3б).
    Арифметика границ остаётся в одном месте — второй её экземпляр разошёлся бы
    с первым при первой же правке окон.
    """
    return _window_forward(period_start, windows.point_a_months)


def window_b(period_end: date, windows: Windows) -> list[date]:
    """Месяцы, по которым считается точка Б."""
    return sorted(_window_backward(period_end, windows.point_b_months))


def baseline_window(period_start: date, windows: Windows) -> list[date]:
    """Месяцы ДО старта работ, которые просит версия порогов.

    Пусто при `pre_start_baseline_months: 0` — опция ТЗ «показать, что рост
    начался после старта работ» по умолчанию выключена. Если её включат на
    калибровке, эти месяцы придётся покупать: с 11.09.2026 сбор берёт запас до
    старта ровно по этому полю, а не безусловно.
    """
    return sorted(
        _shift(period_start, -offset) for offset in range(1, windows.pre_start_baseline_months + 1)
    )


def _window_forward(anchor: date, months: int) -> list[date]:
    return [_shift(anchor, offset) for offset in range(months)]


def _window_backward(anchor: date, months: int) -> list[date]:
    return [_shift(anchor, -offset) for offset in range(months)]


def _shift(anchor: date, months: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)
