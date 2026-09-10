"""Приём списка целиком: файл → проекты в базе → отчёт.

Примеры приёмки: B1 (сто строк, семь негодных), B5 (повторная загрузка не
удваивает проекты). Тесты идут против настоящего postgres: `upsert` опирается на
`UniqueConstraint` и на кортежный `IN`, и подмена базы на память проверяла бы
другой код.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.intake.accept import (
    SourceNotFoundError,
    UnknownSourceError,
    accept,
    read_source,
)
from ahrefs_cases.intake.csv_source import read_csv
from ahrefs_cases.intake.rejections import RejectReason
from ahrefs_cases.storage.models.project import Project

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)

GOOD_ROWS = 93
BAD_ROWS: list[tuple[str, RejectReason]] = [
    (
        ",2025-01-01,2026-01-01,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.MISSING_FIELD,
    ),
    (
        "   ,2025-01-01,2026-01-01,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.MISSING_FIELD,
    ),
    (
        "не домен,2025-01-01,2026-01-01,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.INVALID_DOMAIN,
    ),
    (
        "1.2.3.4,2025-01-01,2026-01-01,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.IP_ADDRESS,
    ),
    (
        "late.example.com,2026-01-01,2025-01-01,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.PERIOD_ORDER,
    ),
    (
        "noclient.example.com,2025-01-01,2026-01-01,fintech,US,seo,10,,i.petrov,yes,subdomains,",
        RejectReason.MISSING_FIELD,
    ),
    (
        "badgeo.example.com,2025-01-01,2026-01-01,fintech,Германия,seo,10,Acme,i.petrov,yes,subdomains,",
        RejectReason.BAD_GEO,
    ),
]


def _list_file(path: Path) -> Path:
    lines = [COLUMNS]
    lines.extend(
        f"d{index}.example.com,2025-01-01,2026-06-30,fintech,US,linkbuilding,"
        f"{index},Acme Ltd,i.petrov,yes,subdomains,"
        for index in range(GOOD_ROWS)
    )
    lines.extend(row for row, _reason in BAD_ROWS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def _count_projects(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Project))).scalar_one()


async def test_hundred_rows_seven_rejected(db_session: AsyncSession, tmp_path: Path) -> None:
    """B1: 93 проекта в базе, семь строк в отчёте с причинами; исключения нет."""
    table = read_csv(_list_file(tmp_path / "list.csv"))

    report = await accept(db_session, table)

    assert report.accepted == GOOD_ROWS
    assert report.created == GOOD_ROWS
    assert report.rejected_rows == len(BAD_ROWS)
    assert await _count_projects(db_session) == GOOD_ROWS


async def test_each_bad_row_gets_its_reason(db_session: AsyncSession, tmp_path: Path) -> None:
    """B1: причина отказа названа по каждой строке, а не «файл не принят».

    Проверяется соответствие строка → причина, потому что общего числа отказов
    недостаточно: семь отказов «строка битая» выглядели бы так же.
    """
    table = read_csv(_list_file(tmp_path / "list.csv"))

    report = await accept(db_session, table)

    for offset, (_row, expected) in enumerate(BAD_ROWS):
        row_no = GOOD_ROWS + offset + 2  # +2: заголовок и нумерация с единицы
        reasons = {item.reason for item in report.rejections if item.row_no == row_no}
        assert expected in reasons, f"строка {row_no}: ожидали {expected}, получили {reasons}"


async def test_reload_updates_and_does_not_duplicate(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B5: повторная загрузка того же файла обновляет, а не создаёт вторые 93."""
    table = read_csv(_list_file(tmp_path / "list.csv"))
    await accept(db_session, table)

    again = await accept(db_session, table)

    assert again.created == 0
    assert again.updated == GOOD_ROWS
    assert await _count_projects(db_session) == GOOD_ROWS


async def test_changed_field_is_applied_on_reload(db_session: AsyncSession, tmp_path: Path) -> None:
    """Обновление обязано что-то менять: иначе `updated=93` было бы пустым словом."""
    path = tmp_path / "list.csv"
    header_and_row = [
        COLUMNS,
        "d0.example.com,2025-01-01,2026-06-30,fintech,US,linkbuilding,10,Acme,i.petrov,yes,subdomains,",
    ]
    path.write_text("\n".join(header_and_row) + "\n", encoding="utf-8")
    await accept(db_session, read_csv(path))

    header_and_row[1] = header_and_row[1].replace(",10,Acme,", ",99,Acme Renamed,")
    path.write_text("\n".join(header_and_row) + "\n", encoding="utf-8")
    await accept(db_session, read_csv(path))

    project = (await db_session.execute(select(Project))).scalars().one()
    assert (project.work_volume, project.client) == (99, "Acme Renamed")


async def test_same_domain_different_period_is_two_projects(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Один домен с разными периодами работ — два кейса, а не дубль.

    Обратная сторона B5: если бы ключом был домен, второй период молча затёр бы
    первый, и агентство потеряло бы кейс прошлого года.
    """
    path = tmp_path / "two.csv"
    path.write_text(
        "\n".join(
            [
                COLUMNS,
                "same.example.com,2024-01-01,2024-12-31,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
                "same.example.com,2025-01-01,2025-12-31,fintech,US,seo,20,Acme,i.petrov,yes,subdomains,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = await accept(db_session, read_csv(path))

    assert report.created == 2
    assert await _count_projects(db_session) == 2


async def test_duplicate_in_source_is_reported(db_session: AsyncSession, tmp_path: Path) -> None:
    """Дубль внутри файла: побеждает последняя строка, обе видны в отчёте."""
    path = tmp_path / "dup.csv"
    path.write_text(
        "\n".join(
            [
                COLUMNS,
                "dup.example.com,2025-01-01,2025-12-31,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,первая",
                "www.dup.example.com,2025-01-01,2025-12-31,fintech,US,seo,20,Acme,i.petrov,yes,subdomains,вторая",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = await accept(db_session, read_csv(path))

    assert report.created == 1
    assert RejectReason.DUPLICATE_IN_SOURCE in report.by_reason()
    project = (await db_session.execute(select(Project))).scalars().one()
    assert project.notes == "вторая"


async def test_missing_column_is_one_rejection_not_hundred(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Нет колонки — брак файла: одна строка в отчёте, а не сто одинаковых."""
    path = tmp_path / "no_client.csv"
    path.write_text(
        "\n".join(
            [
                COLUMNS.replace(",client", ",klient"),
                "a.example.com,2025-01-01,2025-12-31,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
                "b.example.com,2025-01-01,2025-12-31,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = await accept(db_session, read_csv(path))

    assert report.accepted == 0
    assert report.by_reason() == {RejectReason.MISSING_COLUMN: 1}
    assert await _count_projects(db_session) == 0


def test_unknown_source_is_named() -> None:
    """`.pdf` вместо списка — внятный отказ, а не `AttributeError` в разборе.

    Формат судится раньше существования файла: сказать про `.pdf` «файл не
    найден» значит отправить человека искать файл, который всё равно не прочтут.
    """
    with pytest.raises(UnknownSourceError):
        read_source("список.pdf")


def test_missing_file_is_named_too(tmp_path: Path) -> None:
    """Опечатка в пути — самая частая ошибка запуска, и отвечать на неё
    трассировкой `io.open` значит требовать чтения стека ради строки «файла нет»."""
    with pytest.raises(SourceNotFoundError, match="файл не найден"):
        read_source(tmp_path / "нет-такого.csv")
