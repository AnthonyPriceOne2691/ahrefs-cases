"""Скрины в PDF-брифе: на листе, в PDF, через загрузчик и из базы.

Примеры приёмки поставки `screenshots-pdf`: M54 (скрин на листе картинкой с
подписью, строка шаблона называет их число), M55 (PDF с настоящим PNG собирается,
лист «Динамика» по-прежнему одна страница), M56 (загрузчик пускает только целые
PNG и JPEG из `data:`, остальное — отказ сборки коротким текстом), M57 (сборка
кейса читает скрины из базы и с диска, пропавший и битый файл — пропуск с записью
в журнал), M58 (подпись скрина проходит запрет стран), M59 (рендер импортирован, а
обрезанный скрин при загрузке — всё равно отказ словами).
"""

from __future__ import annotations

import base64
import logging
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from tests.sheet_pages import sheet_pages

from ahrefs_cases import config
from ahrefs_cases.cases.model import CaseData, CaseImage, Change, Period
from ahrefs_cases.cases.screens import load_screens
from ahrefs_cases.cases.stoplist import check
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.export import pdf_renderer
from ahrefs_cases.export.brief_sheet import brief_sections
from ahrefs_cases.export.html_renderer import render_html
from ahrefs_cases.storage._enums import Group
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.screenshot import ProjectScreenshot
from ahrefs_cases.storage.screenshots import ScreenshotRejectedError, prepare, save


def _png(color: str = "white", fmt: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (480, 300), color).save(buffer, format=fmt)
    return buffer.getvalue()


def _broken_png() -> bytes:
    """PNG с испорченной контрольной суммой данных: открывается, но не целый."""
    raw = bytearray(_png())
    raw[raw.find(b"IDAT") + 6] ^= 0xFF
    return bytes(raw)


def _data(mime: str, content: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def _case(*images: CaseImage) -> CaseData:
    change = Change("org_traffic", Delta(before=1000.0, after=2600.0, absolute=1600.0, pct=160.0))
    return CaseData(
        title="tours.example",
        anonymized=False,
        geo="DE",
        niche="путешествия",
        service="seo",
        period=Period(start=date(2024, 10, 1), end=date(2025, 9, 1)),
        work_volume=120,
        group=Group.GOOD,
        ruleset_version="2026-10-A",
        changes=(change,),
        domain="tours.example",
        screenshots=images,
    )


SHOT = CaseImage(kind="ahrefs", caption="Обзор · Германия (DE)", mime="image/png", content=_png())


def test_screen_is_on_the_sheet_as_a_picture_with_its_caption() -> None:
    """M54: картинка `data:` внутри листа, подпись с видом; строка шаблона называет число."""
    html = render_html(_case(SHOT))
    ai = CaseImage("ai", "ChatGPT", "image/png", _png("black"))

    assert 'src="data:image/png;base64,' in html
    assert "Отчёт Ahrefs · Обзор · Германия (DE)" in html
    assert _told(_case(SHOT)) == "1 шт. — в разделе «Скрины» ниже"
    assert _told(_case(SHOT, ai)).endswith("ниже; там же видимость в ИИ — 1 шт.")
    assert _told(_case()).startswith("ещё не загружены")
    assert _told(_case(ai)).endswith("видимость в ИИ — 1 шт. в разделе «Скрины» ниже")


def _told(case: CaseData) -> str:
    rows = {row.label: row.value for section in brief_sections(case) for row in section.rows}
    return rows["Скрины результатов работ из Ahrefs"]


def test_pdf_with_a_real_png_builds_and_the_sheet_stays_one_page(tmp_path: Path) -> None:
    """M55: настоящий PNG проходит загрузчик; лист «Динамика» — одна страница."""
    case = _case(SHOT, CaseImage("ai", "ChatGPT", "image/png", _png("black")))

    rendered = pdf_renderer.render_pdf(case, output_dir=tmp_path)

    assert rendered.path.read_bytes()[:5] == b"%PDF-"
    assert sheet_pages(render_html(case)) == 1


@pytest.mark.parametrize(
    "url",
    [
        _data("text/html", b"<script>"),
        _data("image/png", b"not a png at all"),
        _data("image/png", _broken_png()),
        _data("image/jpeg", _png(fmt="JPEG")[: len(_png(fmt="JPEG")) // 2]),
        _data("image/png", _png(fmt="JPEG")),
        "https://app.ahrefs.com/logo.png",
    ],
    ids=["html", "not-a-picture", "broken-png", "cut-jpeg", "jpeg-as-png", "network"],
)
def test_fetcher_lets_through_only_whole_pictures(url: str) -> None:
    """M56: чужой тип, битая, обрезанная и не та картинка, внешний адрес — отказ сборки."""
    with pytest.raises(pdf_renderer.NetworkAccessDeniedError):
        pdf_renderer._DenyNetwork()(url)


def test_refusal_names_the_reason_without_the_picture(tmp_path: Path) -> None:
    """M56: текст отказа — причина словами, а не мегабайты base64 в журнале и строке прогона."""
    case = _case(CaseImage("ahrefs", "Обзор", "image/png", _broken_png()))

    with pytest.raises(pdf_renderer.NetworkAccessDeniedError) as caught:
        pdf_renderer.render_pdf(case, output_dir=tmp_path)

    assert (
        str(caught.value)
        == "скрин в брифе не собрать: картинка повреждена: прочитать её не удалось"
    )
    assert not list(tmp_path.iterdir())


async def test_build_reads_screens_from_the_database_and_the_disk(
    db_session: AsyncSession,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M57: скрины — в порядке загрузки; пропавший и битый файл пропущены и названы в журнале."""
    monkeypatch.setattr(config.export, "screenshots_dir", tmp_path)
    project = Project(
        domain="screens-build.example",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="travel",
        geo="DE",
        service_type="seo",
        client="Acme",
        owner="i.p",
        publishable=True,
    )
    db_session.add(project)
    await db_session.flush()
    prepared = prepare(_png())
    kept = save(tmp_path, project.id, prepared)
    damaged = f"{project.id}/damaged.png"
    (tmp_path / damaged).write_bytes(_broken_png())
    rows = ((kept, "есть"), (f"{project.id}/gone.png", "пропал"), (damaged, "битый"))
    for key, caption in rows:
        db_session.add(
            ProjectScreenshot(
                project_id=project.id,
                kind="ahrefs",
                caption=caption,
                storage_key=key,
                mime="image/png",
                width=prepared.width,
                height=prepared.height,
                size_bytes=len(prepared.content),
                checksum=caption.ljust(64, "0"),
            )
        )
    await db_session.flush()

    with caplog.at_level(logging.WARNING, logger="ahrefs_cases.cases.screens"):
        images = await load_screens(db_session, project.id)

    assert [image.caption for image in images] == ["есть"]
    assert images[0].content == prepared.content
    told = [record.msg for record in caplog.records]
    assert told == ["screenshot_missing_for_case", "screenshot_damaged_for_case"]


def test_screen_caption_goes_through_the_country_ban() -> None:
    """M58: подпись печатается на листе — значит проходит запрет, как текст кейса."""
    hits = check(_case(CaseImage("ai", "ответ Яндекса", "image/png", _png())))

    assert [hit.where for hit in hits] == ["подпись скрина"]


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_cut_upload_is_refused_even_next_to_the_renderer(fmt: str) -> None:
    """M59: модуль рендера импортирован (как в API и воркере) — обрезанный файл не дорисовывается."""
    whole = _png("navy", fmt=fmt)

    with pytest.raises(ScreenshotRejectedError, match="повреждена"):
        prepare(whole[: len(whole) // 2])
