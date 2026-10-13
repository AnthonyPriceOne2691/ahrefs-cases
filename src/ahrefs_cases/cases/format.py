"""Как число выглядит в кейсе. Один формат на текст, таблицу и график.

Живёт в `cases`, а не в рендере, потому что текст кейса ниже рендера по слоям и
импортировать его не может. Два форматтера разошлись бы в первый же день: в
таблице «47 326», в предложении «47326» — и читатель решил бы, что это разные
числа.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

THOUSANDS = " "
"""Неразрывный пробел: «47 326» не должно разрываться переносом строки."""

PERCENT = "\u00a0%"
"""Знак процента — через неразрывный пробел, по той же причине: перенос оставлял
«+640» в конце строки листа, а «%» уносил на следующую (Z56)."""


def number(value: float) -> str:
    """Число как в отчёте.

    Дробная часть показывается только у маленьких величин: «58,4» у Domain
    Rating осмысленно, «113 312,0» визитов — шум. Половина — от нуля, как на
    экране (`_rounded`, Z63).
    """
    if abs(value) < 10 and value != int(value):
        return f"{_rounded(value, 1):.1f}".replace(".", ",")
    return f"{int(_rounded(value, 0)):,}".replace(",", THOUSANDS)


def percent(value: float | None) -> str:
    """Рост процентом — или «с нуля», если базы не было.

    `None` приходит из `classify/deltas`, когда точка А была нулевой: «+∞ %» и
    «+1200 %» от единицы одинаково бессмысленны, а «было 0, стало 12» — нет.
    Половина — от нуля, как у `number`.
    """
    if value is None:
        return "с нуля"
    digits = 0 if abs(value) >= 10 else 1
    return f"{_rounded(value, digits):+.{digits}f}{PERCENT}".replace(".", ",")


def _rounded(value: float, digits: int) -> Decimal:
    """Величина, округлённая до `digits` знаков: половина — от нуля, как на экране.

    Встроенный `round` и формат `:.1f` округляют половину к чётному, а карточка
    печатает числа `toLocaleString` браузера — от нуля: точка А ссылающихся
    доменов jupid.com, среднее 582,5, была «582» в PDF и «583» в карточке (Z63).
    Половину браузер ищет в записи числа — кратчайшей, той же, что даёт `repr`, —
    а не в двоичном значении: 2,15 у него «2,2», хотя двоичная дробь — 2,1499…
    Поэтому `Decimal(repr(value))`, а не `Decimal(value)`. Целое — через
    `to_integral_value`: у `quantize` потолок в 28 знаков.
    """
    written = Decimal(repr(value))
    if digits == 0:
        return written.to_integral_value(rounding=ROUND_HALF_UP)
    return written.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
