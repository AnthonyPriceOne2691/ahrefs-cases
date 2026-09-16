"""Ось периодов: риски под каждым месяцем и подписи, которые человек узнаёт.

Отдельно от `charts`, потому что ось — своё правило, а не деталь кривой: шаг
подписей берётся из лестницы узнаваемых, а последний период подписывается
всегда. Координаты приходят готовыми — где стоит месяц, знает рисунок.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ahrefs_cases.export.labels import text

LABEL_WIDTH = 26.0
"""Место под подпись «01.24» вместе с зазором, в единицах холста."""

_NICE_STEPS = (1, 2, 3, 6, 12)
"""Шаги подписей, которые человек узнаёт: месяц, два, квартал, полгода, год."""

MUTED = "#898781"
"""Цвет оси: подписи и риски приглушены — ось не спорит с кривой."""


def label_step(count: int, room_width: float) -> int:
    """Через сколько точек подписывать ось.

    Прежде шаг считался как «примерно пять подписей на ось»
    (`round(len(months) / 4)`), и на восемнадцати месяцах выходил каждый
    четвёртый: 01.24, 05.24, 09.24… Такой ритм не читается ни как месяц, ни как
    квартал — владелец так и сказал: «стоит месяц, а снизу не месяц» (15.09.2026).

    Теперь шаг берётся из лестницы узнаваемых (1, 2, 3, 6, 12) — наименьший, чей
    ряд подписей влезает по ширине. На восемнадцати месяцах это каждый второй,
    на трёх годах — полугодие.
    """
    room = max(1, int(room_width // LABEL_WIDTH))
    for step in _NICE_STEPS:
        if -(-count // step) <= room:
            return step
    return max(1, -(-count // room))


def month_ticks(xs: Sequence[float], step: int, *, base: float) -> str:
    """Короткая риска под КАЖДЫМ месяцем, подписанные — длиннее.

    Подписей на оси меньше, чем месяцев: они не влезают. Без рисок месяцы между
    подписями не видно вовсе — владелец так и сказал: «81 месяц, потом 10, потом
    12-й, а 9 и 11-й как будто и не видны» (15.09.2026). Риска возвращает им
    место на оси, не занимая ширины подписи.
    """
    return "".join(
        f'<line x1="{x:.1f}" y1="{base:.1f}" '
        f'x2="{x:.1f}" y2="{base + (4.5 if index % step == 0 else 2.5):.1f}" '
        f'stroke="{MUTED}" stroke-width="{0.9 if index % step == 0 else 0.6}" opacity="0.7"/>'
        for index, x in enumerate(xs)
    )


def month_labels(months: Sequence[date], xs: Sequence[float], *, baseline: float) -> str:
    """Подписи оси. Последний месяц подписан ВСЕГДА.

    Без него ось обрывалась молча: конец кривой подписан значением (83 184), а
    каким месяцем — нет, и период приходилось достраивать в уме. Если ближайшая
    подпись слева мешает последней, она уступает: две налезающие подписи хуже
    одной.
    """
    if not months:
        return ""
    at = dict(zip(months, xs, strict=True))
    step = label_step(len(months), xs[-1] - xs[0] if len(xs) > 1 else LABEL_WIDTH)
    shown = [month for index, month in enumerate(months) if index % step == 0]
    last = months[-1]
    if shown and shown[-1] != last:
        if at[last] - at[shown[-1]] < LABEL_WIDTH:
            shown.pop()
        shown.append(last)
    return "".join(
        text(
            at[month],
            baseline,
            f"{month.month:02d}.{month.year % 100:02d}",
            size=7.5,
            fill=MUTED,
            anchor="middle",
        )
        for month in shown
    )
