"""Лист брифа: пункты шаблона, ссылки на отчёты Ahrefs и запрет стран по брифу.

Примеры приёмки поставки `brief-pdf`: M33 (каждый пункт брифа на листе, порядок
шаблона, что сервис знает сам), M35 (ссылки на отчёты: домен, режим, страна,
период), M37 (запрет RU/BY читает клиента и бриф).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from weasyprint import CSS, HTML
from weasyprint.formatting_structure import boxes

from ahrefs_cases.cases.model import CaseData, Change, Period
from ahrefs_cases.cases.stoplist import ContentBlockedError, check
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.export import pdf_renderer
from ahrefs_cases.export.ahrefs_links import report_links
from ahrefs_cases.export.brief_sheet import EMPTY, brief_sections, printed_fields
from ahrefs_cases.export.html_renderer import render_html
from ahrefs_cases.storage._enums import Group
from ahrefs_cases.storage.brief import FIELDS, SECTIONS


def _case(**overrides: object) -> CaseData:
    change = Change("org_traffic", Delta(before=1000.0, after=2600.0, absolute=1600.0, pct=160.0))
    fields: dict[str, object] = {
        "title": "tours.example",
        "anonymized": False,
        "geo": "DE",
        "niche": "путешествия",
        "service": "seo",
        "period": Period(start=date(2024, 10, 1), end=date(2025, 9, 1)),
        "work_volume": 120,
        "group": Group.GOOD,
        "ruleset_version": "2026-10-A",
        "changes": (change,),
        "domain": "tours.example",
        "owner": "Пётр",
        "client": "ООО «Туры»",
    }
    fields.update(overrides)
    return CaseData(**fields)  # type: ignore[arg-type]


def _rows(case: CaseData) -> dict[str, str]:
    return {row.label: row.value for section in brief_sections(case) for row in section.rows}


PX_PER_MM = 96 / 25.4
WIDE_FONT = CSS(string='body { font-family: Verdana, "DejaVu Sans", sans-serif !important; }')
"""Широкий шрифт — как DejaVu Sans, которым лист печатается в контейнере прода (Z55).

Шаблон просит системные шрифты; на Mac они узкие, и длинная подпись до значения не
дотягивала — дефект был виден только на проде. Verdana — на Mac, DejaVu Sans — в CI."""


def _label_cells(html: str) -> list[tuple[boxes.TableCellBox, boxes.TableCellBox]]:
    """Пары «подпись — значение» таблиц листа брифа в вёрстке WeasyPrint (L45: мерить)."""
    document = HTML(string=html).render(stylesheets=[WIDE_FONT])
    pairs = []
    for page in document.pages:
        for row in page._page_box.descendants():  # вёрстку страницы WeasyPrint отдаёт только так
            if not isinstance(row, boxes.TableRowBox):
                continue
            cells = [cell for cell in row.children if isinstance(cell, boxes.TableCellBox)]
            if len(cells) == 2 and "brief-table__label" in (cells[0].element.get("class") or ""):
                pairs.append((cells[0], cells[1]))
    return pairs


def _text_right(cell: boxes.TableCellBox) -> float:
    return max(
        text.position_x + text.width
        for text in cell.descendants()
        if isinstance(text, boxes.TextBox)
    )


def test_label_keeps_its_distance_from_the_value() -> None:
    """M117: подпись не упирается в значение — «…какие услуги делали» и «заполняет специалист»."""
    pairs = _label_cells(render_html(_case()))

    assert len(pairs) == len(FIELDS) + 7 + 3  # пункты брифа, семь своих сервиса, три ссылки Ahrefs
    gap = 4 * PX_PER_MM
    for label, value in pairs:
        # M117: отступ подписи 4 мм доходит до вёрстки, а текст кончается не ближе 4 мм к значению
        assert label.padding_right == pytest.approx(gap, abs=0.01), label.element.text
        assert value.content_box_x() - _text_right(label) >= gap - 0.01, label.element.text


def test_every_brief_field_is_on_the_sheet_in_template_order() -> None:
    """M33: пункта брифа, которого нет на листе, не бывает; разделы — в порядке шаблона."""
    assert printed_fields() == {field.key for field in FIELDS}
    assert tuple(section.title for section in brief_sections(_case())) == SECTIONS


def test_sheet_fills_what_the_service_knows_and_marks_the_rest() -> None:
    """M33: кто вёл, услуга, период, гео и рост — сами; тематика и объём — из файла,
    пока их не заполнили; пункт списка — подписью; пустое — «заполняет специалист»."""
    rows = _rows(_case(brief={"site_type": "marketplace", "goals": "топ-10 по турам"}))

    assert rows["Кто из сотрудников вёл проект"] == "Пётр"
    assert rows["Услуга (по которой пишем кейс)"] == "SEO-продвижение"
    assert rows["Период сотрудничества"] == "10.2024 — 09.2025 (12 мес.)"
    assert rows["ГЕО"] == "Германия (DE)"
    assert rows["Процент роста показателей"] == "органический трафик +160\u00a0%"  # M118
    assert rows["Тематика"] == "путешествия"
    assert rows["Бюджет проекта / объём работ"] == "120 (объём работ из файла)"
    assert rows["Тип сайта"] == "Маркетплейс"
    assert rows["Поставленные цели"] == "топ-10 по турам"
    assert rows["Трудности, которые возникли"] == ""
    assert EMPTY in render_html(_case())


def test_links_carry_domain_mode_country_and_period() -> None:
    """M35: по каждой стране — три отчёта команды; период — от трёх месяцев до старта."""
    links = report_links(
        "tours.example", "subdomains", "DE,AT", date(2024, 10, 1), date(2025, 9, 1)
    )

    assert [link.country for link in links] == ["Германия (DE)"] * 3 + ["Австрия (AT)"] * 3
    overview = parse_qs(urlsplit(links[0].url).query)
    assert urlsplit(links[0].url).path == "/site-explorer/overview"
    assert overview["target"] == ["tours.example/"]
    assert overview["mode"] == ["subdomains"]
    assert overview["country"] == ["de"]
    assert overview["chartInterval"] == ["2024-07-01|2025-09-01"]
    keywords = parse_qs(urlsplit(links[4].url).query)
    assert keywords["country"] == ["at"]
    assert "chartInterval" not in parse_qs(urlsplit(links[2].url).query)


def test_worldwide_links_ask_for_all_countries() -> None:
    """M35: весь мир — один набор ссылок «по всем странам»."""
    links = report_links("tours.example", "subdomains", "WW", date(2024, 10, 1), date(2025, 9, 1))

    assert [link.country for link in links] == ["Весь мир"] * 3
    assert parse_qs(urlsplit(links[0].url).query)["country"] == ["all"]
    assert parse_qs(urlsplit(links[1].url).query)["country"] == ["allByLocation"]
    assert f'href="{links[0].url.replace("&", "&amp;")}"' in render_html(_case(geo="WW"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"brief": {"difficulties": "просели позиции в Яндексе"}},
        {"client": "ООО «Москва-Туры»"},
    ],
)
def test_stoplist_reads_the_brief_and_the_client(
    overrides: dict[str, object], tmp_path: Path
) -> None:
    """M37: что печатается — проверяется: бриф и клиент тоже, и файла при срабатывании нет."""
    case = _case(**overrides)

    assert check(case)
    with pytest.raises(ContentBlockedError):
        pdf_renderer.render_pdf(case, output_dir=tmp_path)
    assert not list(tmp_path.iterdir())
