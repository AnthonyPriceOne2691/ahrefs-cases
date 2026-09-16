"""Кривые кейса: ряды, геометрия SVG и лист с двумя графиками.

Примеры приёмки поставки `case-charts`: E1 (дыра не интерполируется), E2
(помесячный топ-10), E3 (некупленная метрика), E4 (отметка старта), E5 (окна А
и Б), E6 (расхождение последнего месяца и точки Б видно), E7 (кириллица), E8
(градиент), E9 (лист остаётся одностраничным), E10 (детерминированность).

Вид графика выбран владельцем из двух собранных прототипов: плоские данные,
объём даёт оформление. Тесты держат не красоту, а то, на чём она стоит, —
что кривая рисуется по измеренным месяцам и не врёт про шкалу.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from itertools import combinations, pairwise
from pathlib import Path

from dateutil.relativedelta import relativedelta

from ahrefs_cases.cases.builder import VerdictView, build_case
from ahrefs_cases.cases.model import CaseSeries
from ahrefs_cases.classify.points import KW_TOP10, Point
from ahrefs_cases.export import pdf_renderer
from ahrefs_cases.export.charts import _LEFT, SUBJECT_COLORS, curves_svg
from ahrefs_cases.export.html_renderer import render_html
from ahrefs_cases.storage._enums import Group, Metric
from ahrefs_cases.storage.models.project import Project

START = date(2025, 3, 1)
END = date(2026, 2, 1)


def _months(count: int, first: date = date(2025, 1, 1)) -> list[date]:
    return [
        date(first.year + (first.month - 1 + i) // 12, (first.month - 1 + i) % 12 + 1, 1)
        for i in range(count)
    ]


def _series(subject: str, values: list[float], months: list[date] | None = None) -> CaseSeries:
    months = months or _months(len(values))
    return CaseSeries(subject=subject, points=tuple(zip(months, values, strict=True)))


def _project(**overrides: object) -> Project:
    fields: dict[str, object] = {
        "id": 1,
        "domain": "example.com",
        "period_start": START,
        "period_end": END,
        "niche": "fintech",
        "geo": "US",
        "service_type": "seo",
        "client": "Acme",
        "owner": "i.petrov",
        "publishable": True,
        "work_volume": 10,
        "notes": "",
    }
    fields.update(overrides)
    return Project(**fields)


def _verdict(months_used: int = 3) -> VerdictView:
    point = lambda at: Point(  # noqa: E731 — короткая фабрика точки, не логика
        at=at, values={Metric.ORG_TRAFFIC: 1000.0}, derived={}, months_used=months_used
    )
    return VerdictView(
        group=Group.GOOD, ruleset_version="2026-09-A", point_a=point(START), point_b=point(END)
    )


def _label_x(svg: str, text: str) -> tuple[float, str]:
    """Координата и выравнивание подписи с заданным текстом.

    Тег ищется целиком, а атрибуты разбираются из него: одним выражением с
    необязательной группой `text-anchor` ловится «start» всегда — жадный
    `[^>]*` съедает атрибут раньше, чем до него дойдёт очередь.
    """
    # Тот же текст бывает и на оси Y — подпись значения отличается кеглем 10.
    matches = [
        found.group(1)
        for found in re.finditer(rf"<text ([^>]*)>{re.escape(text)}</text>", svg)
        if 'font-size="10"' in found.group(1)
    ]
    assert matches, f"подписи {text!r} кеглем 10 нет в рисунке"
    attributes = matches[0]
    x = re.search(r'x="([\d.]+)"', attributes)
    anchor = re.search(r'text-anchor="(\w+)"', attributes)
    assert x, "у подписи нет координаты"
    return float(x.group(1)), anchor.group(1) if anchor else "start"


def test_long_value_label_stays_inside_the_frame() -> None:
    """Подпись точки Б не уезжает за край рисунка.

    Найдено глазами на готовом PDF: у `ahrefs.com` величина семизначная, и
    «3 596 464» превратилось в «3 596 46…». В разметке обрезания нет — режет
    `viewBox` при растеризации, поэтому проверяется геометрия (класс L84).
    """
    months = _months(3)
    svg = curves_svg(
        [_series("org_traffic", [900_000.0, 2_000_000.0, 3_596_464.0], months)],
        period_start=months[0],
        window_b=months[-1:],
        point_b={"org_traffic": 3_596_464.0},
    )

    x, anchor_kind = _label_x(svg, "3\u00a0596\u00a0464")

    # Справа места нет — подпись переходит на другую сторону отметки, но
    # остаётся целиком внутри `viewBox`: срезает её растеризация, а не разметка.
    width = len("3 596 464") * 5.8
    left = x - width if anchor_kind == "end" else x
    assert left >= 0.0 and left + width <= 420.0, "подпись вышла за холст"


def test_missing_month_is_not_interpolated() -> None:
    """E1: кривая рисуется по измеренным месяцам, без сглаживания и подстановок."""
    months = _months(6)
    del months[2]
    svg = curves_svg(
        [_series("org_traffic", [10.0, 20.0, 40.0, 50.0, 60.0], months)], period_start=months[0]
    )

    path = re.search(r'd="(M[^"]+)" fill="none"', svg)  # сама линия, не заливка
    assert path is not None
    assert path.group(1).count("L") == 4  # пять точек — четыре отрезка
    assert "C" not in path.group(1)  # кривых Безье нет, значит нет и сглаживания


def test_monthly_top10_needs_both_buckets() -> None:
    """E2: месяц с одной корзиной пропускается, а не считается половиной."""
    months = _months(3)
    series = {
        Metric.KW_TOP3: dict(zip(months, [10.0, 11.0, 12.0], strict=True)),
        Metric.KW_TOP4_10: {months[0]: 20.0, months[2]: 24.0},
    }
    case = build_case(_project(), _verdict(), series)

    by_subject = {item.subject: item for item in case.series}
    assert by_subject[KW_TOP10].points == ((months[0], 30.0), (months[2], 36.0))


def test_metric_never_bought_draws_nothing() -> None:
    """E3: пустые оси сказали бы «роста не было» (урок L30)."""
    assert curves_svg([], period_start=START) == ""
    assert curves_svg([_series("org_traffic", [10.0])], period_start=START) == ""


def test_start_of_works_is_marked_and_earlier_months_are_dimmed() -> None:
    """E4: отметка «старт работ» — требование ТЗ, а не украшение."""
    months = _months(6)
    svg = curves_svg(
        [_series("org_traffic", [10.0, 12.0, 14.0, 18.0, 22.0, 26.0], months)],
        period_start=months[2],
    )

    assert "старт работ" in svg
    assert 'opacity="0.04"' in svg  # приглушённые месяцы до старта


def test_windows_of_points_a_and_b_are_shown() -> None:
    """E5 и E6: последний месяц кривой не равен точке Б, и кейс это показывает.

    Точка Б — среднее по окну, последний месяц — одно измерение. Рядом на листе
    без окна это читается как ошибка в одном из двух чисел.
    """
    months = _months(6)
    svg = curves_svg(
        [_series("org_traffic", [10.0, 12.0, 14.0, 18.0, 22.0, 26.0], months)],
        period_start=months[1],
        window_a=months[1:3],
        window_b=months[-2:],
    )

    assert svg.count('opacity="0.05"') == 2
    assert ">А</text>" in svg
    assert ">Б</text>" in svg


def test_every_text_carries_an_explicit_font() -> None:
    """E7: без `font-family` WeasyPrint расставляет кириллицу по буквам (L43)."""
    svg = curves_svg([_series("org_traffic", [10.0, 20.0, 30.0])], period_start=START)

    texts = re.findall(r"<text[^>]*>", svg)
    assert texts
    assert all("font-family=" in tag for tag in texts)


def test_gradient_stops_are_opaque() -> None:
    """E8: `stop-opacity` меньше единицы гасит заливку в PDF целиком (L43)."""
    svg = curves_svg([_series("org_traffic", [10.0, 20.0, 30.0])], period_start=START)

    assert 'fill="url(#curve-fill)"' in svg
    assert svg.count('stop-opacity="1"') == 2
    assert SUBJECT_COLORS["org_traffic"] in svg


def test_case_with_two_charts_still_fits_one_page(tmp_path: Path) -> None:
    """E9: две кривые не уводят кейс на вторую страницу."""
    months = _months(16, date(2024, 12, 1))
    case = build_case(
        _project(),
        _verdict(),
        {
            Metric.ORG_TRAFFIC: dict(
                zip(months, [1000.0 + 200 * i for i in range(16)], strict=True)
            ),
            Metric.KW_TOP3: dict(zip(months, [50.0 + i for i in range(16)], strict=True)),
            Metric.KW_TOP4_10: dict(zip(months, [120.0 + 3 * i for i in range(16)], strict=True)),
        },
    )

    html = render_html(case)
    rendered = pdf_renderer.render_pdf(case, output_dir=tmp_path)

    assert html.count("<svg") == 2
    assert "Динамика органического трафика" in html
    assert "Динамика позиций" in html
    assert rendered.pages == 1


def test_svg_is_deterministic() -> None:
    """E10: геометрия считается от данных, а не от порядка обхода."""
    series = [_series("org_traffic", [10.0, 20.0, 30.0])]
    assert curves_svg(series, period_start=START) == curves_svg(series, period_start=START)


def test_chart_carries_its_own_paper() -> None:
    """E1 и E2: рисунок несёт свою бумагу, а не полагается на чужую.

    Найдено тёмной темой веб-карточки: чернила выбраны под белый лист, заливка
    затухает в цвет полотна, а самого полотна в разметке не было — на тёмном
    фоне подписи значений сливались (урок L82).

    Проверяется, что подложка идёт **первой** (иначе она закроет кривые) и
    покрывает весь холст, включая подписи осей и легенду.
    """
    from ahrefs_cases.export.charts import SURFACE, curves_svg

    svg = curves_svg(
        [
            CaseSeries(
                subject=Metric.ORG_TRAFFIC.value,
                points=((date(2025, 1, 1), 10.0), (date(2025, 2, 1), 20.0)),
            )
        ],
        period_start=date(2025, 1, 1),
    )

    body = svg.split("</defs>", 1)[1]
    assert body.startswith("<rect"), "подложка обязана идти под всем остальным"
    assert f'fill="{SURFACE}"' in body
    # Холст 420×210: подложка меньше только на толщину рамки.
    assert 'width="419"' in body
    assert 'height="209"' in body


def test_empty_series_draw_no_paper() -> None:
    """E3: рядов нет — рисунка нет вовсе, подложка в одиночку не появляется."""
    from ahrefs_cases.export.charts import curves_svg

    assert curves_svg([], period_start=date(2025, 1, 1)) == ""


def test_axis_step_is_recognisable_and_the_last_month_is_named() -> None:
    """Подписи оси идут узнаваемым шагом, и конец периода назван.

    Владелец смотрел `ahrefs.com` на шаге «месяц» и увидел снизу 01.24, 05.24,
    09.24 — каждый четвёртый месяц: «стоит месяц, а снизу не месяц»
    (15.09.2026). Шаг считался как «примерно пять подписей на ось» и попадал в
    число, которое не читается ни как месяц, ни как квартал.

    Проверяется два свойства: шаг взят из лестницы узнаваемых (месяц, два,
    квартал, полгода, год) и последний месяц подписан — без него ось
    обрывалась молча, и период приходилось достраивать в уме.
    """
    months = [date(2024, 1, 1) + relativedelta(months=index) for index in range(18)]
    values = [1000.0 + index * 100 for index in range(18)]
    svg = curves_svg([_series("org_traffic", values, months)], period_start=months[0])

    # Сортировка по ВРЕМЕНИ, а не по паре (месяц, год): иначе январь 2025-го
    # встаёт между январём и мартом 2024-го, и шаг считается по мусору.
    ordered = sorted(
        date(2000 + int(year), int(month), 1)
        for month, year in re.findall(r">(\d{2})\.(\d{2})</text>", svg)
    )
    assert ordered, "подписей оси нет вовсе"

    # Первый и последний месяцы названы: это границы периода.
    assert ordered[0] == months[0]
    assert ordered[-1] == months[-1]
    gaps = {
        (later.year - earlier.year) * 12 + later.month - earlier.month
        for earlier, later in pairwise(ordered)
    }
    assert gaps <= {1, 2, 3, 6, 12}, f"шаг подписей не узнаётся: {sorted(gaps)}"


def test_point_a_is_marked_with_its_own_value() -> None:
    """Точка А подписана СВОИМ значением — средним по окну, а не месяцем.

    До 16.09.2026 рисунок выделял крайние месяцы, а таблица показывала средние
    по окну: у `bad.org.uk` в таблице «102 478», а на кривой «68 961», и это
    читалось как ошибка сервиса. Владелец: «зачем нам средние?» Средние нужны
    методу (один месяц-выброс иначе делает рост из ничего), поэтому рисунок
    стал показывать то же, что таблица (Z32).
    """
    months = _months(6)
    svg = curves_svg(
        [_series("org_traffic", [36980.0, 40000.0, 52000.0, 61000.0, 74000.0, 83184.0], months)],
        period_start=months[0],
        window_a=months[:2],
        window_b=months[-2:],
        point_a={"org_traffic": 38_490.0},
        point_b={"org_traffic": 78_592.0},
    )

    # Разряды разделены НЕРАЗРЫВНЫМ пробелом: поиск с обычным ничего не найдёт.
    assert "38\u00a0490" in svg, "точка А не подписана своим значением"
    assert "78\u00a0592" in svg, "точка Б не подписана своим значением"
    # Подпись точки А растёт ВЛЕВО: справа от её окна идёт сама кривая.
    left = re.search(r'<text[^>]*x="([\d.]+)"[^>]*text-anchor="end"[^>]*>38\u00a0490</text>', svg)
    assert left, "подпись точки А не прижата влево — значит может лечь на кривую"


def test_every_month_gets_a_tick_even_without_a_label() -> None:
    """Под каждым месяцем — риска, даже если подписи у него нет.

    Подписей на оси меньше, чем месяцев: они не влезают. Без рисок месяцы между
    подписями не видно вовсе — «9 и 11-й как будто и не видны» (15.09.2026).
    """
    months = _months(12)
    svg = curves_svg(
        [_series("org_traffic", [float(i + 1) * 100 for i in range(12)])], period_start=months[0]
    )

    base = 210.0 - 30.0  # _HEIGHT - _BOTTOM
    ticks = re.findall(rf'<line[^>]*y1="{base:.1f}"[^>]*y2="(?:18[0-9]|1[89][0-9])[.\d]*"', svg)
    assert len(ticks) >= 12, f"рисок меньше, чем месяцев: {len(ticks)}"


# --- Z28: подписи не наслаиваются друг на друга -----------------------------
#
# Мерка здесь СВОЯ, а не взятая у рисовальщика: оракул, считающий ширину той же
# функцией, что и код, зеленеет вместе с ошибкой в ней. Знак Arial ужат до
# 0,52 кегля (у цифры 0,556, у пробела 0,278) — оценка снизу, чтобы тест ловил
# настоящие столкновения, а не законную тесноту.


@dataclass(frozen=True)
class _Box:
    """Место, которое подпись занимает на холсте."""

    left: float
    right: float
    top: float
    bottom: float
    body: str
    size: float

    def hits(self, other: _Box) -> bool:
        return (
            self.left < other.right
            and other.left < self.right
            and self.top < other.bottom
            and other.top < self.bottom
        )


def _boxes(svg: str) -> list[_Box]:
    """Прямоугольники всех подписей рисунка."""
    boxes = []
    for found in re.finditer(r"<text ([^>]*)>([^<]*)</text>", svg):
        attributes, body = found.group(1), found.group(2)
        x = float(re.search(r'x="(-?[\d.]+)"', attributes).group(1))
        y = float(re.search(r'y="(-?[\d.]+)"', attributes).group(1))
        size = float(re.search(r'font-size="([\d.]+)"', attributes).group(1))
        anchor = re.search(r'text-anchor="(\w+)"', attributes)
        kind = anchor.group(1) if anchor else "start"
        width = len(body) * 0.52 * size
        left = x - width if kind == "end" else x - width / 2 if kind == "middle" else x
        boxes.append(_Box(left, left + width, y - size * 0.72, y + size * 0.05, body, size))
    return boxes


def _collisions(svg: str) -> list[tuple[str, str]]:
    boxes = _boxes(svg)
    return [
        (first.body, second.body) for first, second in combinations(boxes, 2) if first.hits(second)
    ]


def _point_centres(svg: str) -> list[float]:
    """Центры отметок А и Б: к ним подписи обязаны остаться близко."""
    return [
        float(found.group(1))
        for found in re.finditer(r'<circle cx="[\d.]+" cy="([\d.]+)" r="3\.4"', svg)
    ]


def test_value_labels_of_two_curves_do_not_overlap() -> None:
    """Близкие величины двух кривых не садятся друг на друга.

    Показано владельцем 15.09.2026 на готовых кейсах (Z28): на графике позиций
    две кривые, обе подписи старта прижаты влево к одному `x`, и при близких
    значениях тексты сливались в кашу — «41 152» поверх «39 880». То же справа
    у конечных величин.
    """
    months = _months(8)
    top10 = _series(
        KW_TOP10, [41_152.0, 41_600, 42_000, 42_400, 42_900, 43_200, 43_400, 43_600], months
    )
    top3 = _series(
        "kw_top3", [39_880.0, 40_100, 40_500, 40_900, 41_400, 41_700, 41_900, 42_100], months
    )

    svg = curves_svg([top10, top3], period_start=months[0])

    assert not _collisions(svg), f"подписи наслаиваются: {_collisions(svg)}"


def test_value_label_does_not_land_on_the_axis_label() -> None:
    """Подпись старта и деление шкалы делят левое поле — и расходятся.

    Второй механизм Z28: величина в точке старта уходит влево (справа от точки
    идёт кривая), а там же стоят подписи шкалы. Когда точка старта оказывается
    на высоте линии сетки, два числа встают одно на другое.
    """
    months = _months(6)
    # Старт почти на половине шкалы: деление шкалы встаёт на ту же высоту, но
    # числа разные — наложение видно как каша, а не как одна подпись.
    series = _series("refdomains", [42_300.0, 43_500, 44_000, 60_000, 75_000, 86_000], months)

    svg = curves_svg([series], period_start=months[0])

    assert not _collisions(svg), f"подписи наслаиваются: {_collisions(svg)}"


def test_labels_stay_next_to_their_points_when_nobody_is_in_the_way() -> None:
    """Раскладка не двигает то, что и так стоит свободно.

    Страж от перегиба: разводить подписи, которым никто не мешает, значит
    отрывать число от его точки — рисунок соврал бы про то, где измерено.
    """
    months = _months(6)
    svg = curves_svg(
        [_series("org_traffic", [10_000.0, 20_000, 30_000, 45_000, 60_000, 90_000], months)],
        period_start=months[0],
        window_a=months[:1],
        window_b=months[-1:],
        point_a={"org_traffic": 10_000.0},
        point_b={"org_traffic": 90_000.0},
    )

    centres = _point_centres(svg)
    values = [
        box for box in _boxes(svg) if box.body in {"10\u00a0000", "90\u00a0000"} and box.size >= 9
    ]
    assert len(values) == 2, "подписаны обе точки"
    for box in values:
        baseline = box.bottom - box.size * 0.05
        assert any(abs(baseline - 3.5 - centre) < 0.2 for centre in centres), (
            f"подпись {box.body!r} уехала от своей точки без причины"
        )


def test_spread_labels_stay_close_to_their_points() -> None:
    """Разведённая подпись остаётся у своей точки, а не уезжает на середину холста.

    Двенадцать единиц — это строка с просветом плюс обход деления шкалы, если
    оно попалось по дороге: больше значит, что подпись ищет себе место уже не
    рядом с точкой, и связь числа с кривой теряется.
    """
    months = _months(8)
    top10 = _series(
        KW_TOP10, [41_152.0, 41_600, 42_000, 42_400, 42_900, 43_200, 43_400, 43_600], months
    )
    top3 = _series(
        "kw_top3", [39_880.0, 40_100, 40_500, 40_900, 41_400, 41_700, 41_900, 42_100], months
    )

    svg = curves_svg([top10, top3], period_start=months[0])

    centres = _point_centres(svg)
    for box in _boxes(svg):
        if " " not in box.body or box.size < 9:
            continue  # деления шкалы кеглем 8 и подписи месяцев не двигаются
        baseline = box.bottom - box.size * 0.05
        assert min(abs(baseline - 3.5 - centre) for centre in centres) <= 12.0, (
            f"подпись {box.body!r} оторвана от точки больше чем на 12 единиц"
        )


def test_labels_never_leave_the_canvas() -> None:
    """Разведение не имеет права вытолкнуть подпись за рамку рисунка."""
    months = _months(4)
    # Обе кривые упираются в потолок шкалы: разводить некуда, кроме как вниз.
    svg = curves_svg(
        [
            _series(KW_TOP10, [99_000.0, 99_200, 99_400, 99_600], months),
            _series("kw_top3", [98_800.0, 98_900, 99_000, 99_100], months),
        ],
        period_start=months[0],
    )

    for box in _boxes(svg):
        assert box.top >= 0.0 and box.bottom <= 210.0, f"подпись {box.body!r} вышла за холст"


def test_labels_keep_the_order_of_their_values() -> None:
    """Выше стоит подпись большей величины — даже когда обеим тесно.

    У `ebsco.com` обе кривые стартуют у самого дна шкалы: места под делением
    «0» не нашлось ни одной подписи, обе ушли вверх, и меньшая села выше
    большей. Рисунок начал говорить неправду о том, какая кривая где
    начинается, хотя наложения уже не было.
    """
    months = _months(6)
    svg = curves_svg(
        [
            _series(KW_TOP10, [8_286.0, 60_000, 180_000, 300_000, 420_000, 440_322], months),
            _series("kw_top3", [2_383.0, 20_000, 60_000, 90_000, 100_000, 101_470], months),
        ],
        period_start=months[0],
        window_a=months[:1],
        point_a={KW_TOP10: 8_286.0, "kw_top3": 2_383.0},
    )

    # Разряды разделены неразрывным пробелом — в разметке это `\xa0`.
    bigger, smaller = "8\u00a0286", "2\u00a0383"
    starts = {box.body: box.top for box in _boxes(svg) if box.body in {bigger, smaller}}
    assert len(starts) == 2, "подписаны обе точки старта"
    assert starts[bigger] < starts[smaller], "подпись большей величины обязана стоять выше"


def test_scale_makes_room_for_points_a_and_b() -> None:
    """Потолок шкалы считается и по точкам А и Б, а не только по месяцам.

    Крайние узлы кривой — это они: у `engoo.com` точка Б равна 454 при
    месячном максимуме 400, и кружок вылезал за верхнюю кромку холста
    (квартальный и годовой шаг, 16.09.2026).
    """
    months = _months(4)
    svg = curves_svg(
        [_series("org_traffic", [100.0, 300, 400, 380], months)],
        period_start=months[0],
        window_b=months[-2:],
        point_b={"org_traffic": 454.0},
    )

    tops = [
        float(found.group(1))
        for found in re.finditer(r'<circle cx="[\d.]+" cy="([\d.]+)" r="3\.4"', svg)
    ]
    assert tops, "отметка не нарисована"
    assert all(value >= 22.0 for value in tops), "отметка вышла за верхнюю кромку"


def test_window_band_does_not_swallow_the_chart() -> None:
    """После свёртки окно раздувается до периода — полосу тогда не рисуем.

    На годовом шаге полоса А закрывала половину рисунка и переставала значить
    «здесь усреднено»; остаётся одна буква у кромки.
    """
    months = _months(4)
    svg = curves_svg(
        [_series("org_traffic", [100.0, 200, 300, 400], months)],
        period_start=months[0],
        window_a=months,
    )

    assert ">А</text>" in svg, "буква окна осталась"
    wide = re.findall(r'<rect x="[\d.]+" y="22.0" width="([\d.]+)"', svg)
    assert all(float(width) <= (420.0 - 62.0 - 62.0) / 3 for width in wide), "полоса съела рисунок"
