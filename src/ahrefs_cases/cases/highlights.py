"""Что подсветить в кейсе: правило выбора метрик и их порядок.

Подсветка — не украшение, а утверждение о результате: то, что в неё попало,
клиент прочитает первым и запомнит. Поэтому правило простое и проверяемое
глазами, без весов и очков.

1. **Подсвечивается только рост.** Упавшая метрика остаётся в блоке «А → Б» —
   прятать её нельзя, — но в подсветку не идёт: кейс не хвалится падением.
2. **Трафик первым.** Он главная метрика по ТЗ, и группа проекта определяется
   им. Кейс, где первым стоит Domain Rating, обсуждать будут не о результате.
3. **Рост от нулевой базы идёт последним и без процента.** «Было 0, стало 12» —
   честное утверждение; «+1200 %» от единицы — нет.
"""

from __future__ import annotations

from collections.abc import Sequence

from ahrefs_cases.cases.model import Change
from ahrefs_cases.storage._enums import Metric

HIGHLIGHT_LIMIT = 3
"""Сколько метрик подсвечиваем. Три, потому что подсветка всего — это не
подсветка: в блоке «А → Б» метрики и так все."""


def pick(changes: Sequence[Change], *, limit: int = HIGHLIGHT_LIMIT) -> tuple[Change, ...]:
    """Выбрать метрики под подсветку в порядке показа."""
    grown = [change for change in changes if change.grew]
    traffic = [change for change in grown if change.subject == Metric.ORG_TRAFFIC.value]
    rest = sorted((change for change in grown if change not in traffic), key=_rank)
    return tuple((traffic + rest)[:limit])


def _rank(change: Change) -> tuple[int, float, float]:
    """Сначала метрики с процентом — по нему, потом рост от нуля.

    При равных процентах решает абсолютный прирост: между двумя «+30 %» в кейс
    просится тот, где это тысяча визитов, а не тридцать.
    """
    from_zero = change.pct is None
    return (int(from_zero), -(change.pct or 0.0), -change.absolute)
