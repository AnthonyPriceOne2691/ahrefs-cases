"""Раскладка подписей на рисунке: где число встанет, чтобы не сесть на соседа.

Живёт отдельно от `charts`, потому что это самостоятельное правило, а не деталь
кривой: рисунок решает, ЧТО подписать, раскладка — ГДЕ. Заведено ради Z28
(16.09.2026): подписи размещались каждая сама по себе — величина в точке
старта, величина в конце, деления шкалы, — и столкновений не проверял никто.

Двигается ТОЛЬКО подпись: точка на кривой остаётся там, где измерено
(требование владельца 15.09.2026 — «двигать можно подпись, но не точку»).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, pairwise

FONT = "Arial, Helvetica, sans-serif"
"""У каждого `<text>` явный `font-family`: без него WeasyPrint расставляет
кириллицу по буквам — надпись «старт работ» превращается в «с т а р т»."""

INK = "#0b0b0b"

DIGIT_WIDTH = 5.8
"""Ширина знака в Arial 10px, с запасом. Нужна, чтобы **посчитать**, влезает ли
подпись справа от точки и делят ли две подписи одну полосу по горизонтали.

Найдено глазами на готовом PDF 12.09.2026: у `ahrefs.com` последнее значение —
семизначное, и подпись «3 596 464» уехала за границу `viewBox`, превратившись в
«3 596 46…». В разметке SVG она не обрезана — режет её растеризация, поэтому ни
один тест на строку такого не увидит (тот же класс, что урок L84, где срезалась
легенда)."""

_LINE_GAP = 1.6
"""Просвет между двумя подписями, в единицах холста: меньше — и числа читаются
как одно многозначное."""

_SPREAD_PASSES = 6
"""Сколько раз первый проход идёт по подписям. Сдвиг одной пары может создать
столкновение с третьей подписью, поэтому проход повторяется, пока двигать
нечего; шесть — потолок от вечного цикла, а не расчёт."""


def text(
    x: float,
    y: float,
    body: str,
    *,
    size: float,
    fill: str,
    anchor: str = "start",
    weight: str = "400",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{body}</text>'
    )


@dataclass(frozen=True)
class Mark:
    """Подпись на холсте: где её базовая линия, что написано и куда смотрит текст.

    Заведена ради Z28. Подписи размещались каждая сама по себе — величина в
    точке старта, величина в конце, деления шкалы, — и столкновений никто не
    проверял: у двух кривых позиций старты садились друг на друга, а подпись
    старта делила левое поле с подписью шкалы. Чтобы развести, нужно знать
    место каждой подписи ДО того, как она стала строкой разметки.
    """

    x: float
    y: float
    body: str
    size: float
    anchor: str
    fill: str = INK
    weight: str = "700"

    @property
    def width(self) -> float:
        """Оценка ширины по числу знаков — той же меркой, что и подпись конца.

        Точной ширины у нас нет: шрифт меряет растеризатор, а мы пишем разметку.
        Оценка сверху (`DIGIT_WIDTH` — знак Arial 10px с запасом) годится для
        обоих дел, ради которых она нужна: влезает ли подпись в поле и делят ли
        две подписи одну полосу по горизонтали.
        """
        return len(self.body) * DIGIT_WIDTH * self.size / 10.0

    @property
    def left(self) -> float:
        return self.x - self.width if self.anchor == "end" else self.x

    def shares_column(self, other: Mark) -> bool:
        """Делят ли подписи полосу по горизонтали.

        Без этой проверки раскладка разводила бы подпись старта (она слева) и
        подпись конца (справа), которые и так не мешают друг другу, — и увела
        бы обе от своих точек без всякой причины.
        """
        return self.left < other.left + other.width and other.left < self.left + self.width

    def required_gap(self, other: Mark) -> float:
        return max(self.size, other.size) * 0.9 + _LINE_GAP

    def draw(self, y: float) -> str:
        return text(
            self.x,
            y,
            self.body,
            size=self.size,
            fill=self.fill,
            anchor=self.anchor,
            weight=self.weight,
        )


def spread(movable: Sequence[Mark], fixed: Sequence[Mark], *, field: tuple[float, float]) -> str:
    """Разводит подписи значений по вертикали и рисует их.

    Двигается ТОЛЬКО подпись: точка на кривой остаётся там, где измерено
    (требование владельца 15.09.2026 — «двигать можно подпись, но не точку»).
    Деления шкалы стоят намертво по той же причине: они привязаны к линии
    сетки, и сдвиг превратил бы их в неправду, — поэтому приходят сюда как
    `fixed`, то есть как препятствие, а не как участник.

    `field` — полоса, в которой подписи имеют право стоять: её границы знает
    рисунок (ниже идут подписи месяцев, выше — кромка холста), и приходят они
    сюда параметром, а не через размеры чужого холста.

    Два прохода, и второй нужен не меньше первого. Сначала столкнувшаяся пара
    расходится симметрично, по половине нехватки каждой: так обе остаются
    рядом со своими точками, а порядок подписей сверху вниз остаётся порядком
    величин. Потом каждая подпись садится на ближайшее СВОБОДНОЕ место —
    с оглядкой на препятствия, на уже размещённых соседей и на края холста.

    Второй проход появился после живого прогона по двенадцати собранным
    кейсам: у `ebsco.com` и `legal-partners.pl` кривые лежат на самом дне
    шкалы, симметричное разведение упирало подпись в нижний край, обрезка по
    краю возвращала её обратно — и она садилась на деление «0». Край холста —
    такое же препятствие, как чужая подпись, и обходить его надо так же.
    """
    ys = _pushed_apart(movable)
    taken = [_band(mark, mark.y) for mark in fixed]
    spots = dict.fromkeys(range(len(movable)), 0.0)
    for index in sorted(range(len(movable)), key=lambda number: ys[number]):
        y = _free_spot(movable[index], ys[index], taken, field)
        taken.append(_band(movable[index], y))
        spots[index] = y
    placed = _in_order(movable, spots)
    return "".join(movable[index].draw(placed[index]) for index in range(len(movable)))


def _in_order(movable: Sequence[Mark], spots: dict[int, float]) -> dict[int, float]:
    """Порядок подписей сверху вниз обязан повторять порядок величин.

    Места ищутся по очереди, и тесный низ шкалы умеет их перепутать: у
    `ebsco.com` обе кривые стартуют у самого дна, места под делением «0» не
    нашлось ни одной, и подпись меньшей величины села выше подписи большей —
    рисунок стал говорить неправду о том, какая кривая где начинается.

    Перестановка безопасна: меняются местами уже найденные свободные места
    между подписями одного кегля и одной стороны, то есть одинаковых по
    геометрии, — новых столкновений появиться неоткуда.
    """
    result = dict(spots)
    kinds: dict[tuple[float, str], list[int]] = {}
    for index, mark in enumerate(movable):
        kinds.setdefault((mark.size, mark.anchor), []).append(index)
    for indexes in kinds.values():
        if len(indexes) < 2:
            continue
        if not all(
            movable[first].shares_column(movable[second])
            for first, second in combinations(indexes, 2)
        ):
            continue
        by_value = sorted(indexes, key=lambda index: movable[index].y)
        for index, y in zip(by_value, sorted(result[index] for index in indexes), strict=True):
            result[index] = y
    return result


def _pushed_apart(movable: Sequence[Mark]) -> list[float]:
    """Первый проход: столкнувшиеся подписи расходятся симметрично."""
    ys = [mark.y for mark in movable]
    for _ in range(_SPREAD_PASSES):
        moved = False
        order = sorted(range(len(movable)), key=lambda index: ys[index])
        for upper, lower in pairwise(order):
            if not movable[upper].shares_column(movable[lower]):
                continue
            lack = movable[upper].required_gap(movable[lower]) - (ys[lower] - ys[upper])
            if lack > 0:
                ys[upper] -= lack / 2
                ys[lower] += lack / 2
                moved = True
        if not moved:
            break
    return ys


def _band(mark: Mark, y: float) -> tuple[float, float, float, float]:
    """Место подписи на холсте вместе с обязательным просветом вокруг."""
    half = _LINE_GAP / 2
    return (
        mark.left,
        mark.left + mark.width,
        y - mark.size * 0.75 - half,
        y + mark.size * 0.25 + half,
    )


def _free_spot(
    mark: Mark,
    wanted: float,
    taken: Sequence[tuple[float, float, float, float]],
    field: tuple[float, float],
) -> float:
    """Ближайшая к желаемой высота, на которой подпись никого не задевает.

    Кандидаты — сама желаемая высота и позиции вплотную над и под каждым
    занятым местом: свободное место, если оно есть, всегда прижато к
    чему-нибудь. Не нашлось ни одного — подпись остаётся у своей точки:
    рисунок с наложением честнее рисунка, где число уехало неизвестно куда.
    """
    above = mark.size * 0.25 + _LINE_GAP / 2
    below = mark.size * 0.75 + _LINE_GAP / 2
    candidates = [wanted]
    for _, _, top, bottom in taken:
        candidates.extend((top - above, bottom + below))
    candidates.append(field[0] + below)
    candidates.append(field[1] - above)
    for candidate in sorted(candidates, key=lambda value: abs(value - wanted)):
        if _fits(mark, candidate, taken, field):
            return candidate
    return wanted


def _fits(
    mark: Mark,
    y: float,
    taken: Sequence[tuple[float, float, float, float]],
    field: tuple[float, float],
) -> bool:
    left, right, top, bottom = _band(mark, y)
    if top < field[0] or bottom > field[1]:
        return False
    return not any(
        left < other_right and other_left < right and top < other_bottom and other_top < bottom
        for other_left, other_right, other_top, other_bottom in taken
    )
