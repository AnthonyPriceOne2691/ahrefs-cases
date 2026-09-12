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
from datetime import date
from pathlib import Path

from ahrefs_cases.cases.builder import VerdictView, build_case
from ahrefs_cases.cases.model import CaseSeries
from ahrefs_cases.classify.points import KW_TOP10, Point
from ahrefs_cases.export import pdf_renderer
from ahrefs_cases.export.charts import SUBJECT_COLORS, curves_svg
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


def test_long_end_value_label_stays_inside_the_frame() -> None:
    """Подпись последнего значения не уезжает за край рисунка.

    Найдено глазами на готовом PDF живого прогона: у `ahrefs.com` последнее
    значение семизначное, и «3 596 464» превратилось в «3 596 46…». В разметке
    SVG обрезания нет — режет `viewBox` при растеризации, поэтому проверять
    надо **геометрию**, а не наличие текста (тот же класс, что L84).
    """
    svg = curves_svg(
        [_series("org_traffic", [900_000.0, 2_000_000.0, 3_596_464.0])],
        period_start=START,
    )

    x, anchor_kind = _label_x(svg, "3\u00a0596\u00a0464")

    assert anchor_kind == "end", "справа места нет — подпись разворачивается влево"
    assert x <= 420.0, "и остаётся внутри viewBox шириной 420"


def test_short_end_value_label_stays_on_the_right() -> None:
    """Короткому числу места хватает, и оно остаётся справа от точки.

    Разворачивать подпись всегда было бы проще и хуже: слева от точки идёт
    кривая, и подпись легла бы на неё.
    """
    svg = curves_svg(
        [_series("org_traffic", [100.0, 200.0, 320.0])],
        period_start=START,
    )

    _, anchor_kind = _label_x(svg, "320")

    assert anchor_kind == "start"


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
