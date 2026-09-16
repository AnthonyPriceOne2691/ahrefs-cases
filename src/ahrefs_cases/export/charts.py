"""Кривые кейса в SVG — один рисунок для PDF и для веб-карточки.

Вид выбран владельцем 11.09.2026 из двух собранных прототипов: **данные
плоские, объём даёт оформление**. Изометрия выглядела дороже, но её верхняя
грань прибавляла каждому столбцу около тысячи визитов на шкале примера, а форма
роста по столбцам читается хуже, чем по линии.

Три правила, каждое оплачено прогоном:

- **Кривая рисуется по измеренным месяцам.** Сглаживания нет: сплайн между
  точками рисует пики и провалы в месяцах, которых мы не мерили, а обсуждать с
  клиентом будут именно их.
- **У каждого `<text>` явный `font-family`.** Без него WeasyPrint расставляет
  кириллицу по буквам — надпись «старт работ» превращается в «с т а р т».
- **Стопы градиента непрозрачные.** `stop-opacity` молча гасит заливку целиком:
  затухание даётся переходом в цвет полотна, а не в прозрачность.

Библиотеки рисования здесь нет намеренно: это сотня строк геометрии, а
зависимость пришлось бы ставить на сервер агентства и отдельно проверять её
поведение в печати.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date

from ahrefs_cases.cases.model import KW_TOTAL, CaseSeries
from ahrefs_cases.classify.points import KW_TOP10
from ahrefs_cases.export.axis import label_step, month_labels, month_ticks
from ahrefs_cases.export.grouping import Grouping, regroup, regroup_window
from ahrefs_cases.export.grouping import period_start as grouping_start
from ahrefs_cases.export.labels import DIGIT_WIDTH, INK, Mark, spread
from ahrefs_cases.export.labels import text as _text
from ahrefs_cases.storage._enums import Metric

SUBJECT_COLORS: Mapping[str, str] = {
    Metric.ORG_TRAFFIC.value: "#2a78d6",
    KW_TOP10: "#eb6834",
    Metric.KW_TOP3.value: "#1baf7a",
    KW_TOTAL: "#eda100",
    Metric.REFDOMAINS.value: "#e87ba4",
    Metric.ORG_COST.value: "#008300",
    Metric.DR.value: "#4a3aa7",
}
"""Цвет закреплён за метрикой, а не за местом: в плитке, в строке таблицы и на
кривой она одного цвета. Один словарь на шаблон и на рисунок — второй экземпляр
разошёлся бы с первым при первой правке."""

MUTED, HAIRLINE, SURFACE = "#898781", "#e1e0d9", "#fcfcfb"
"""Чернила (`INK`) и шрифт (`FONT`) живут в `export.labels`: подпись и её
раскладка — одно хозяйство."""
_WIDTH, _HEIGHT = 420.0, 210.0
"""Поле слева шире правого: там живут и подписи шкалы, и величина в точке
старта работ. Считали 44 — семизначное «3 596 464» в точке старта не помещалось
и падало внутрь рисунка, на саму кривую (замечание владельца 15.09.2026)."""
_LEFT, _RIGHT, _TOP, _BOTTOM = 54.0, 46.0, 22.0, 30.0
"""Пропорции под колонку в половину листа: два графика ТЗ стоят рядом, потому
что в столбик они уводят кейс на вторую страницу — замерено на готовом PDF."""
_HEADROOM = 1.12
"""Запас над максимумом, чтобы метка последнего значения не упиралась в рамку."""

_FIELD = (_TOP, _HEIGHT - _BOTTOM + 5)
"""Полоса, в которой подписи величин имеют право стоять: ниже идут подписи
месяцев, выше — кромка холста. Раскладка берёт её параметром — границы знает
рисунок, а не она."""


def curves_svg(
    series: Sequence[CaseSeries],
    *,
    period_start: date,
    window_a: Sequence[date] = (),
    window_b: Sequence[date] = (),
    point_a: Mapping[str, float] | None = None,
    point_b: Mapping[str, float] | None = None,
) -> str:
    """Один график: одна или несколько кривых на общей шкале месяцев.

    Пустой список рядов даёт пустую строку, а не пустые оси: «метрику не
    покупали» и «метрика равна нулю» — разные утверждения (урок L30).
    """
    drawable = [item for item in series if len(item.points) >= 2]
    if not drawable:
        return ""

    months = sorted({month for item in drawable for month, _ in item.points})
    top = max(value for item in drawable for _, value in item.points) * _HEADROOM
    parts = [
        _paper(),
        _grid(top),
        _before_start(months, period_start),
        _window_band(months, window_a, "А"),
        _window_band(months, window_b, "Б"),
    ]
    for index, item in enumerate(drawable):
        parts.append(_curve(item, months, top, filled=index == 0))
    start_mark, start_hint = _start_mark(months, period_start)
    parts.append(start_mark)
    # Подписи величин собираются вместе и размещаются одной раскладкой: порознь
    # они садились друг на друга и на деления шкалы (Z28).
    marks: list[Mark] = []
    for item in drawable:
        for point, mark in (
            _point_mark(item, months, top, window_a, (point_a or {}).get(item.subject), "end"),
            _point_mark(item, months, top, window_b, (point_b or {}).get(item.subject), "start"),
        ):
            parts.append(point)
            if mark is not None:
                marks.append(mark)
    obstacles = [*_axis_marks(top), *([start_hint] if start_hint else [])]
    parts.append(spread(marks, obstacles, field=_FIELD))
    xs = [_x(month, months) for month in months]
    room = _WIDTH - _LEFT - _RIGHT
    parts.append(month_ticks(xs, label_step(len(months), room), base=_HEIGHT - _BOTTOM))
    parts.append(month_labels(months, xs, baseline=_HEIGHT - _BOTTOM + 13))
    if len(drawable) > 1:
        parts.append(_legend(drawable))

    gradient = _gradient(drawable[0].subject)
    return (
        f'<svg viewBox="0 0 {_WIDTH:.0f} {_HEIGHT:.0f}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        f"<defs>{gradient}</defs>{''.join(parts)}</svg>"
    )


def _x(month: date, months: Sequence[date]) -> float:
    if len(months) < 2:
        return _LEFT
    step = (_WIDTH - _LEFT - _RIGHT) / (len(months) - 1)
    return _LEFT + months.index(month) * step


def _y(value: float, top: float) -> float:
    return _HEIGHT - _BOTTOM - (value / top) * (_HEIGHT - _BOTTOM - _TOP)


def _number(value: float) -> str:
    return f"{round(value):,}".replace(",", " ")


def _axis_rows(top: float) -> list[tuple[float, str]]:
    """Деления шкалы: базовая линия подписи и что на ней написано.

    Один источник и для сетки, и для раскладки: второй экземпляр разошёлся бы с
    первым, и раскладка обходила бы подписи там, где их нет.
    """
    axis_max = _axis_max(top / _HEADROOM)
    return [
        (_y(axis_max * fraction, top), _number(axis_max * fraction)) for fraction in (0.0, 0.5, 1.0)
    ]


_AXIS_DROP = 3.0
"""На сколько базовая линия подписи шкалы ниже самой линии сетки: цифры стоят
серединой на линии, а не висят над ней."""


def _axis_marks(top: float) -> list[Mark]:
    """Деления шкалы как препятствие для раскладки: место занято, двигать нельзя."""
    return [
        Mark(_LEFT - 7, y + _AXIS_DROP, body, size=8, anchor="end", fill=MUTED, weight="400")
        for y, body in _axis_rows(top)
    ]


def _gradient(subject: str) -> str:
    """Заливка под первой кривой: от цвета метрики к цвету полотна."""
    color = SUBJECT_COLORS[subject]
    return (
        '<linearGradient id="curve-fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="1"/>'
        f'<stop offset="100%" stop-color="{SURFACE}" stop-opacity="1"/>'
        "</linearGradient>"
    )


def _axis_max(value: float) -> float:
    """Верхняя линия сетки — круглое число не выше максимума серии.

    Шкала и подпись — разные вещи: масштаб берёт запас над максимумом, чтобы
    метка последнего значения не упиралась в край, а подписывать этот запас
    числом вида «130 133» значит показывать читателю арифметику отступа.
    """
    if value <= 0:
        return 0.0
    magnitude = float(10 ** (math.floor(math.log10(value)) - 1))
    return float(math.floor(value / magnitude)) * magnitude


def _paper() -> str:
    """Собственная бумага рисунка — под всем остальным.

    Рисунок сделан для печати: чернила тёмные, а заливка под кривой затухает в
    **цвет полотна**. Пока потребитель был один (белый лист PDF), полотно
    подразумевалось и совпадало с настоящим. С Ф6 тот же SVG показывается в
    веб-карточке, а она бывает тёмной — и тогда фона у рисунка нет вовсе:
    подписи значений сливаются, а затухание читается белой дымкой.

    Поэтому подложка едет внутри самого рисунка, а не плашкой на фронте: цвет
    объявлен здесь, и второй его экземпляр в CSS разошёлся бы с этим при первой
    правке. Заодно правильным становится скачанный файл.

    Форма повторяет плитки метрик кейса (скругление, волосяная рамка): на листе
    рисунок стоит с ними в одном ряду, и другая форма читалась бы вставкой.
    """
    return (
        f'<rect x="0.5" y="0.5" width="{_WIDTH - 1:.0f}" height="{_HEIGHT - 1:.0f}" '
        f'rx="6" fill="{SURFACE}" stroke="{HAIRLINE}" stroke-width="1"/>'
    )


def _grid(top: float) -> str:
    lines = []
    for (y, _), mark in zip(_axis_rows(top), _axis_marks(top), strict=True):
        lines.append(
            f'<line x1="{_LEFT}" y1="{y:.1f}" x2="{_WIDTH - _RIGHT}" y2="{y:.1f}" '
            f'stroke="{HAIRLINE}" stroke-width="0.7"/>'
        )
        lines.append(mark.draw(mark.y))
    return "".join(lines)


def _before_start(months: Sequence[date], period_start: date) -> str:
    """Месяцы до старта работ приглушены: это чужой результат, не наш."""
    before = [month for month in months if month < period_start]
    if not before:
        return ""
    width = _x(before[-1], months) - _LEFT
    return (
        f'<rect x="{_LEFT}" y="{_TOP}" width="{width:.1f}" '
        f'height="{_HEIGHT - _BOTTOM - _TOP:.1f}" fill="{INK}" opacity="0.04"/>'
    )


def _window_band(months: Sequence[date], window: Sequence[date], label: str) -> str:
    """Окно, по которому усреднена точка А или Б, и само её значение.

    Показывается, потому что последний месяц кривой и точка Б различаются по
    построению: без окна это выглядит как ошибка в одном из двух чисел.

    Значение подписывается рядом с буквой (16.09.2026). Раньше рисунок нёс
    только реальные месяцы, а таблица — средние по окну, и связать их можно
    было лишь в уме: у `cazoo.co.uk` в таблице «371 292», а конец кривой —
    «262 170». Теперь оба числа стоят на рисунке: среднее у полосы, месяц у
    точки (Z32).
    """
    present = [month for month in window if month in months]
    if not present:
        return ""
    left = _x(present[0], months)
    right = _x(present[-1], months)
    width = max(right - left, 3.0)
    middle = left + width / 2
    band = (
        f'<rect x="{left:.1f}" y="{_TOP}" width="{width:.1f}" '
        f'height="{_HEIGHT - _BOTTOM - _TOP:.1f}" fill="{INK}" opacity="0.05"/>'
    )
    body = label
    # Подпись стоит НАД полосой, а не под осью: внизу живут подписи месяцев и
    # легенда, и «39 127» у окна Б садилось прямо на «ключи в топ-10» — первая
    # же сборка это показала. Наверху пусто, и место там своё.
    #
    # Полоса Б прижата к правому краю, полоса А — к левому, поэтому текст
    # удерживается внутри холста: центрирование по полосе увело бы половину
    # числа за `viewBox`, где его срежет растеризация (тот же класс, что L84).
    half = len(body) * DIGIT_WIDTH * 0.8 / 2
    anchored = min(max(middle, half + 2), _WIDTH - half - 2)
    return band + _text(anchored, _TOP - 6, body, size=8, fill=MUTED, anchor="middle", weight="700")


def _curve(item: CaseSeries, months: Sequence[date], top: float, *, filled: bool) -> str:
    color = SUBJECT_COLORS[item.subject]
    coords = [(_x(month, months), _y(value, top)) for month, value in item.points]
    line = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.1f},{y:.1f}" for index, (x, y) in enumerate(coords)
    )
    parts = []
    if filled:
        base = _HEIGHT - _BOTTOM
        parts.append(
            f'<path d="{line} L{coords[-1][0]:.1f},{base:.1f} L{coords[0][0]:.1f},{base:.1f} Z" '
            'fill="url(#curve-fill)" opacity="0.55"/>'
        )
    # Ореол — две широкие полупрозрачные обводки: размытие фильтром WeasyPrint
    # не рисует, а тень линии нужна ровно для ощущения объёма.
    parts.extend(
        f'<path d="{line}" fill="none" stroke="{color}" stroke-opacity="{opacity}" '
        f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        for width, opacity in ((9, "0.10"), (5, "0.20"))
    )
    parts.append(
        f'<path d="{line}" fill="none" stroke="{color}" stroke-width="2.4" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    parts.append(
        f'<path d="{line}" fill="none" stroke="#ffffff" stroke-opacity="0.35" '
        'stroke-width="0.8" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return "".join(parts)


def _start_mark(months: Sequence[date], period_start: date) -> tuple[str, Mark | None]:
    """Пунктир старта работ и его подпись.

    Подпись возвращается наружу ещё и как препятствие: она стоит у верхней
    кромки, и высокая точка старта целилась бы ровно в неё.
    """
    after = [month for month in months if month >= period_start]
    if not after:
        return "", None
    x = _x(after[0], months)
    mark = Mark(x + 7, _TOP + 5, "старт работ", size=8, anchor="start", fill="#1c5cab")
    return (
        f'<line x1="{x:.1f}" y1="{_TOP}" x2="{x:.1f}" y2="{_HEIGHT - _BOTTOM:.1f}" '
        f'stroke="#1c5cab" stroke-width="1" stroke-dasharray="3 2.5"/>'
        f'<circle cx="{x:.1f}" cy="{_TOP + 2}" r="6" fill="#1c5cab" opacity="0.12"/>'
        f'<circle cx="{x:.1f}" cy="{_TOP + 2}" r="2.6" fill="#1c5cab"/>' + mark.draw(mark.y),
        mark,
    )


def _point_mark(
    item: CaseSeries,
    months: Sequence[date],
    top: float,
    window: Sequence[date],
    value: float | None,
    side: str,
) -> tuple[str, Mark | None]:
    """Точка А или Б на рисунке: уровень среднего по окну, а не месяц.

    До 16.09.2026 кривая выделяла крайние МЕСЯЦЫ, а таблица показывала средние
    по окну, и рядом это читалось как ошибка сервиса: у `bad.org.uk` в таблице
    «102 478», а подписанная точка на кривой — «68 961». Владелец: «зачем нам
    средние?» Средние нужны методу — один удачный месяц иначе делает рост из
    ничего (`classify/points.py`), — поэтому рисунок стал показывать ТО ЖЕ, что
    таблица: уровень точки внутри своего окна (Z32).

    Отметка — горизонтальный штрих во всю ширину окна, а не кружок на кривой:
    среднее двух месяцев на линии не лежит, и кружок обещал бы измерение там,
    где его нет.
    """
    present = [month for month in window if month in months]
    if not present or value is None:
        return "", None
    # Середина окна, но НИКОГДА не за полем графика: после свёртки в кварталы и
    # годы окно схлопывается к краю, и метка уезжала за ось вместе с подписью —
    # показано владельцем 16.09.2026 на квартальном и годовом шаге.
    field_left, field_right = _LEFT, _WIDTH - _RIGHT
    middle = (_x(present[0], months) + _x(present[-1], months)) / 2
    centre = min(max(middle, field_left + 4), field_right - 4)
    y = _y(value, top)
    color = SUBJECT_COLORS[item.subject]
    body = _number(value)
    # Штрих короткий и всегда вокруг своего кружка: во всю ширину окна он на
    # годовом шаге растягивался через полполотна и терял связь с точкой.
    half = 9.0
    left_end = max(centre - half, field_left)
    right_end = min(centre + half, field_right)
    # Подпись уходит туда, где есть место: у окна Б справа, у окна А слева.
    if side == "end":
        anchor_x = max(left_end - 5, len(body) * DIGIT_WIDTH + 2)
    else:
        anchor_x = min(right_end + 5, _WIDTH - len(body) * DIGIT_WIDTH - 2)
    glyph = (
        f'<line x1="{left_end:.1f}" y1="{y:.1f}" x2="{right_end:.1f}" y2="{y:.1f}" '
        f'stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>'
        f'<circle cx="{centre:.1f}" cy="{y:.1f}" r="3.2" fill="#ffffff" '
        f'stroke="{color}" stroke-width="2"/>'
    )
    return glyph, Mark(anchor_x, y + 3.5, body, size=10, anchor=side)


def _legend(series: Sequence[CaseSeries]) -> str:
    """Две кривые и больше — легенда обязательна: цвет не сообщает ничего в одиночку.

    Отступ от нижнего края холста — не вкус: базовая линия стояла ровно на
    границе `viewBox`, и выносные элементы букв («у», «р») срезались всегда.
    Без рамки этого не было видно, а с появлением бумаги легенда ещё и упёрлась
    в неё.
    """
    parts = []
    x = _LEFT
    for item in series:
        parts.append(
            f'<rect x="{x:.1f}" y="{_HEIGHT - 12:.1f}" width="7" height="7" rx="1.5" '
            f'fill="{SUBJECT_COLORS[item.subject]}"/>'
        )
        parts.append(_text(x + 10, _HEIGHT - 6, item.label, size=8, fill=MUTED))
        x += 12 + len(item.label) * 4.6
    return "".join(parts)


CHART_BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Динамика органического трафика", (Metric.ORG_TRAFFIC.value,)),
    ("Динамика позиций", (KW_TOP10, Metric.KW_TOP3.value)),
)
"""Два графика ТЗ и то, из чего каждый состоит.

Позиции — одна картинка на два ряда: топ-10 и вложенный в него топ-3. Порознь
они читались бы как независимые метрики, хотя второй входит в первый."""


def curve_blocks(
    series: Sequence[CaseSeries],
    *,
    period_start: date,
    window_a: Sequence[date] = (),
    window_b: Sequence[date] = (),
    grouping: Grouping = Grouping.MONTH,
    point_a: Mapping[str, float] | None = None,
    point_b: Mapping[str, float] | None = None,
) -> list[dict[str, str]]:
    """Готовые блоки «заголовок + рисунок» — и для PDF, и для веб-карточки.

    Живёт здесь, а не в рендерере HTML, потому что звать её стало двоим:
    кейс и карточка проекта обязаны показывать **один и тот же** рисунок.
    Второй экземпляр компоновки разошёлся бы с первым (шкала, подписи, набор
    рядов), и тогда сотрудник и клиент увидели бы разные кривые одного проекта.

    Ряда нет — графика нет: пустые оси сказали бы «роста не было», хотя мы
    просто не покупали эту метрику.

    `grouping` сворачивает месяцы в кварталы или годы **до** рисования и
    переносит полосы окон А и Б в те же координаты: окно, оставшееся в месяцах,
    просто исчезло бы с оси периодов.
    """
    # Свёртка идёт до рисования: рисовальщик знает только точки, а правило
    # «поток складывается, запас берётся на конец» принадлежит метрике.
    folded = {item.subject: item for item in regroup(series, grouping)}
    bands = (regroup_window(window_a, grouping), regroup_window(window_b, grouping))
    # Дата старта работ сворачивается ТЕМ ЖЕ правилом, что ось. Без этого она
    # оставалась месяцем, а ось после свёртки состоит из начал периодов: метка
    # «старт работ» и пунктир вставали не туда и переезжали при каждой смене
    # шага — на годовом шаге уползали к правому краю рисунка. Найдено владельцем
    # 15.09.2026 на `etymonline.com`: три шага, три разных места старта.
    folded_start = grouping_start(period_start, grouping)
    blocks: list[dict[str, str]] = []
    for title, subjects in CHART_BLOCKS:
        rows = [folded[name] for name in subjects if name in folded]
        # Значения передаются ПО ВСЕМ метрикам блока: на графике позиций две
        # кривые — топ-10 и топ-3, — и у каждой своя точка А и своя Б. Взять
        # только главную значило бы подписать одну кривую и промолчать о второй.
        svg = curves_svg(
            rows,
            period_start=folded_start,
            window_a=bands[0],
            window_b=bands[1],
            point_a=point_a,
            point_b=point_b,
        )
        if svg:
            blocks.append({"title": title, "svg": svg})
    return blocks
