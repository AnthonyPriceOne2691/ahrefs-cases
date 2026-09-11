"""Одностраничный кейс: HTML-шаблон, PDF и контент-запрет.

Примеры приёмки поставки `case-pdf`: E1 (файл PDF), E2 (сноска и атрибуция),
E3 (анонимность), E4 (гео), E5 (текст), E6 (fail-closed), E7 (пустой объём
работ), E8 (числа те же), E9 (детерминированность), E10 (одна страница).

Анонимность проверяется по **HTML и имени файла**, а не по байтам PDF: текст в
PDF закодирован глифами встроенного шрифта, и поиск строки в нём всегда даёт
«не найдено» — оракул, который проходит при любой ошибке, хуже отсутствующего.
HTML при этом единственный источник, из которого PDF собран.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ahrefs_cases.cases.model import CaseData, Change, Period
from ahrefs_cases.cases.stoplist import ContentBlockedError, check
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.export import pdf_renderer
from ahrefs_cases.export.html_renderer import ATTRIBUTION, DATA_FOOTNOTE, number, render_html
from ahrefs_cases.storage._enums import Group

SUBJECTS = ("org_traffic", "kw_top10", "kw_top3", "kw_total", "refdomains", "org_cost", "dr")


def _change(subject: str, before: float, after: float) -> Change:
    absolute = after - before
    pct = (absolute / before) * 100 if before > 0 else None
    return Change(
        subject=subject, delta=Delta(before=before, after=after, absolute=absolute, pct=pct)
    )


def _case(**overrides: object) -> CaseData:
    fields: dict[str, object] = {
        "title": "example.com",
        "anonymized": False,
        "geo": "US",
        "niche": "fintech",
        "service": "linkbuilding",
        "period": Period(start=date(2025, 1, 1), end=date(2026, 6, 1)),
        "work_volume": 120,
        "group": Group.GOOD,
        "ruleset_version": "2026-09-A",
        "changes": tuple(
            _change(subject, 100.0 * index + 100, 250.0 * index + 300)
            for index, subject in enumerate(SUBJECTS)
        ),
    }
    fields.update(overrides)
    return CaseData(**fields)  # type: ignore[arg-type]


def test_pdf_is_written_and_is_a_single_page(tmp_path: Path) -> None:
    """E1 и E10: файл на диске, сигнатура PDF, одна страница на семи метриках."""
    rendered = pdf_renderer.render_pdf(_case(), output_dir=tmp_path)

    assert rendered.path.exists()
    assert rendered.path.read_bytes()[:5] == b"%PDF-"
    assert rendered.pages == 1


def test_required_footnote_and_attribution_are_in_the_html() -> None:
    """E2: сноска про оценку Ahrefs и юридическая формулировка атрибуции.

    «Благодаря работам» — утверждение причинно-следственной связи, которой у
    нас нет: проверяется его отсутствие, а не только наличие правильного текста.
    """
    html = render_html(_case())

    assert DATA_FOOTNOTE in html
    assert ATTRIBUTION in html
    assert "благодаря работ" not in html.lower()


def test_anonymous_case_shows_no_domain(tmp_path: Path) -> None:
    """E3: ни в HTML, ни в имени файла."""
    case = _case(title="сайт в нише travel", anonymized=True, niche="travel")

    html = render_html(case)
    rendered = pdf_renderer.render_pdf(case, output_dir=tmp_path)

    assert "example.com" not in html
    assert "сайт в нише travel" in html
    assert "example" not in rendered.path.name


@pytest.mark.parametrize("geo", ["RU", "by"])
def test_forbidden_geo_blocks_the_artifact(geo: str, tmp_path: Path) -> None:
    """E4: контент-запрет ТЗ ловится структурно, по коду страны."""
    with pytest.raises(ContentBlockedError):
        pdf_renderer.render_pdf(_case(geo=geo), output_dir=tmp_path)


def test_forbidden_text_blocks_the_artifact_and_surfing_does_not() -> None:
    """E5: запрет смотрит на текст кейса, а не только на код страны.

    Вторая половина примера не формальность: «сёрфинг» содержит «рф», и
    подстрочный поиск аббревиатур блокировал бы кейсы за вид спорта.
    """
    blocked = check(_case(niche="доставка из Москвы"))
    assert [hit.matched for hit in blocked] == ["москв"]

    assert check(_case(niche="сёрфинг и туризм", service="серфинг")) == ()


def test_failed_check_leaves_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6: fail-closed — свойство порядка вызовов, а не обработчика ошибок."""

    def explode(_case: CaseData) -> None:
        message = "проверка не отработала"
        raise RuntimeError(message)

    monkeypatch.setattr(pdf_renderer, "ensure_publishable", explode)
    with pytest.raises(RuntimeError):
        pdf_renderer.render_pdf(_case(), output_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_empty_work_volume_leaves_the_block_out() -> None:
    """E7: «что сделали» не выдумывается — как и в структуре кейса."""
    assert "Что сделали" in render_html(_case())
    assert "Что сделали" not in render_html(_case(work_volume=None))


def test_numbers_in_html_are_the_numbers_of_the_case() -> None:
    """E8: форматирование меняет вид, а не значение (урок L41)."""
    case = _case()
    html = render_html(case)

    for change in case.changes:
        assert number(change.before) in html
        assert number(change.after) in html
    assert number(47326.0) == "47\u00a0326"  # неразрывный пробел в тысячах


def test_render_is_deterministic() -> None:
    """E9: один кейс — один HTML."""
    case = _case()
    assert render_html(case) == render_html(case)


def test_template_may_not_reach_the_network(tmp_path: Path) -> None:
    """Рендер не ходит в сеть: сервер агентства может стоять без выхода наружу.

    Запрет — загрузчик ресурсов, а не договорённость: шаблон с внешней
    картинкой обязан обрывать сборку, а не собирать кейс без неё.
    """
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "case.html.j2").write_text(
        '<html><body><img src="https://example.com/logo.png"></body></html>', encoding="utf-8"
    )

    with pytest.raises(pdf_renderer.NetworkAccessDeniedError):
        pdf_renderer.render_pdf(_case(), output_dir=tmp_path, templates_dir=templates)
