"""Приём списка целиком: источник → проверенные проекты в базе → отчёт.

Один вход на все источники и один отчёт на выходе. Здесь же выбирается ридер:
по виду ссылки, а не по параметру — отдел присылает то ссылку, то файл, и
спрашивать у него формат значит спрашивать дважды.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.intake.csv_source import read_csv
from ahrefs_cases.intake.gsheet_source import Fetcher, read_gsheet
from ahrefs_cases.intake.report import IntakeReport
from ahrefs_cases.intake.rows import RawTable
from ahrefs_cases.intake.upsert import upsert_projects
from ahrefs_cases.intake.validate import validate_table
from ahrefs_cases.intake.xlsx_source import read_xlsx

_XLSX_SUFFIXES = (".xlsx", ".xlsm")
_SHEET_MARKER = "docs.google.com/spreadsheets"


class UnknownSourceError(ValueError):
    """Источник не опознан. Отдельный тип: «не знаю, как читать» и «прочитал,
    там пусто» ведут к разным действиям человека."""


def read_source(reference: str | Path, fetch: Fetcher | None = None) -> RawTable:
    """Ссылка или путь → сырая таблица."""
    ref = str(reference)
    if _SHEET_MARKER in ref:
        return read_gsheet(ref, fetch=fetch)

    path = Path(ref)
    if path.suffix.lower() in _XLSX_SUFFIXES:
        return read_xlsx(path)
    if path.suffix.lower() == ".csv":
        return read_csv(path)
    raise UnknownSourceError(
        f"не понимаю источник: {ref}. Ожидаю .csv, .xlsx или ссылку на Google Sheet."
    )


async def accept(session: AsyncSession, table: RawTable) -> IntakeReport:
    """Проверить таблицу и записать годные строки. Отчёт — про всё сразу.

    Порядок «сначала проверить всё, потом писать» намеренный: приём на сто строк
    не должен оставлять базу наполовину заполненной, если сороковая строка
    окажется битой.
    """
    drafts, rejections = validate_table(table)
    result = await upsert_projects(session, drafts)
    return IntakeReport(
        origin=table.origin,
        accepted=len(drafts),
        created=result.created,
        updated=result.updated,
        rejections=tuple(rejections),
    )
