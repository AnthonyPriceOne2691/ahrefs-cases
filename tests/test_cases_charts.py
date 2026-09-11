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
