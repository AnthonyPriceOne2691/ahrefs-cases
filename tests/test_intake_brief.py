"""Колонки брифа во входном файле и правило NDA при повторной загрузке.

Примеры приёмки поставки `brief-columns-intake`: M24 (колонки брифа понимаются
словами), M25 (непонятая ячейка брифа — замечание, строка принята), M26 (пустая
ячейка не стирает дописанное в карточке), M27 (файл ставит NDA, но не снимает).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.intake.rejections import RejectReason
from ahrefs_cases.intake.rows import RawTable
from ahrefs_cases.intake.validate import validate_table
from ahrefs_cases.storage.models.project import Project

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,work_volume,client,owner,"
    "publishable,topic,site_type,client_request,complexity,complexity_note,folder_url"
)
DRIVE = "https://drive.google.com/drive/folders/intake-brief"
DOMAIN = "brief-columns.example.com"


def _row(*, publishable: str = "да", brief: str = ",,,,,") -> str:
    return f"{DOMAIN},2025-01-01,2025-12-01,travel,DE,seo,10,Acme,i.p,{publishable},{brief}"


def _table(row: str) -> RawTable:
    return parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test")


def test_brief_columns_are_read_by_words() -> None:
    """M24: пункт списка пишут словами, ссылку и текст — как есть; хранится ключ."""
    brief = f"Путешествия,маркетплейс,рост заявок из органики,Высокая,сезонность,{DRIVE}"
    drafts, rejections, notices = validate_table(_table(_row(brief=brief)))

    assert not rejections and not notices
    assert drafts[0].brief == {
        "topic": "travel",
        "site_type": "marketplace",
        "client_request": "рост заявок из органики",
        "complexity": "high",
        "complexity_note": "сезонность",
        "folder_url": DRIVE,
    }


def test_unclear_brief_cell_is_a_notice_not_a_rejection() -> None:
    """M25: непонятое не записывается, строка принята, замечание называет ячейку."""
    brief = "Путешествия,космодром,,адская,,https://yadi.sk/d/folder"
    drafts, rejections, notices = validate_table(_table(_row(brief=brief)))

    assert not rejections
    assert drafts[0].brief == {"topic": "travel"}
    by_column = {notice.field: notice for notice in notices}
    assert by_column["site_type"].reason is RejectReason.BAD_ENUM
    assert "космодром" in by_column["site_type"].detail
    assert by_column["complexity"].reason is RejectReason.BAD_ENUM
    assert by_column["folder_url"].reason is RejectReason.BAD_LINK
    assert "yadi.sk" in by_column["folder_url"].detail


async def _project(session: AsyncSession) -> Project:
    found = await session.execute(select(Project).where(Project.domain == DOMAIN))
    return found.scalars().one()


async def test_empty_cell_keeps_what_the_card_says(db_session: AsyncSession) -> None:
    """M26: пустая ячейка — «нет сведений», а не «очистить»: дописанное в карточке живёт."""
    await accept(db_session, _table(_row()))
    project = await _project(db_session)
    project.brief = {"goals": "топ-10", "client_request": "из карточки"}
    await db_session.flush()

    await accept(db_session, _table(_row(brief=",SaaS,,,,")))
    project = await _project(db_session)
    await db_session.refresh(project)

    assert project.brief == {
        "goals": "топ-10",
        "client_request": "из карточки",
        "site_type": "saas",
    }


async def test_file_sets_nda_but_does_not_lift_it(db_session: AsyncSession) -> None:
    """M27: «нет» в файле ставит NDA; «да» снять его не может — только карточка."""
    await accept(db_session, _table(_row(publishable="да")))
    project = await _project(db_session)
    project.publishable = False
    await db_session.flush()

    await accept(db_session, _table(_row(publishable="да")))
    await db_session.refresh(project)
    assert project.publishable is False

    project.publishable = True
    await db_session.flush()
    await accept(db_session, _table(_row(publishable="нет")))
    await db_session.refresh(project)
    assert project.publishable is False
