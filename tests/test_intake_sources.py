"""Три источника — один результат. Примеры приёмки: B2 (источники), B3 (кодировки).

Проверяется не «csv читается», а то, ради чего источники сведены к одному типу:
CSV, XLSX и Google Sheet обязаны дать побайтово одинаковую сырую таблицу. Разойдись
они — расхождение проявилось бы на приёме списка от отдела, а не здесь.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from ahrefs_cases.intake.csv_source import decode, read_csv
from ahrefs_cases.intake.gsheet_source import (
    SheetAccessError,
    SheetLinkError,
    read_gsheet,
    sheet_export_url,
)
from ahrefs_cases.intake.rows import RawTable
from ahrefs_cases.intake.xlsx_source import read_xlsx

HEADER = ["domain", "period_start", "period_end", "client", "notes"]
ROWS = [
    ["example.com", "2025-01-01", "2026-06-30", "Acme Ltd", ""],
    ["example.org", "2024-09-01", "2025-09-01", "Бейшпиль ГмбХ", "сезонная ниша, смотреть YoY"],
]


def _csv_text(delimiter: str = ",") -> str:
    lines = [delimiter.join(HEADER)]
    for row in ROWS:
        cells = [f'"{cell}"' if delimiter in cell else cell for cell in row]
        lines.append(delimiter.join(cells))
    return "\n".join(lines) + "\n"


def _write_xlsx(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(HEADER)
    for row in ROWS:
        sheet.append(row)
    workbook.save(path)
    return path


def _as_tuples(table: RawTable) -> list[tuple[str, ...]]:
    return [tuple(row.get(column) for column in table.columns) for row in table.data_rows()]


def test_three_sources_give_identical_table(tmp_path: Path) -> None:
    """B2: CSV, XLSX и Google Sheet с одинаковым содержимым читаются одинаково."""
    csv_path = tmp_path / "list.csv"
    csv_path.write_text(_csv_text(), encoding="utf-8")
    xlsx_path = _write_xlsx(tmp_path / "list.xlsx")

    from_csv = read_csv(csv_path)
    from_xlsx = read_xlsx(xlsx_path)
    from_sheet = read_gsheet(
        "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0",
        fetch=lambda _url: _csv_text().encode("utf-8"),
    )

    assert from_csv.columns == from_xlsx.columns == from_sheet.columns == tuple(HEADER)
    assert _as_tuples(from_csv) == _as_tuples(from_xlsx) == _as_tuples(from_sheet)


def test_semicolon_delimiter_is_detected(tmp_path: Path) -> None:
    """B17: Excel в русской локали сохраняет CSV с `;` — файл читается как есть."""
    path = tmp_path / "ru.csv"
    path.write_text(_csv_text(delimiter=";"), encoding="utf-8")

    table = read_csv(path)

    assert table.columns == tuple(HEADER)
    assert _as_tuples(table)[0][0] == "example.com"


def test_cp1251_is_read_without_mojibake(tmp_path: Path) -> None:
    """B3: кириллица из cp1251-выгрузки читается текстом, а не «кракозябрами»."""
    path = tmp_path / "cp1251.csv"
    path.write_bytes(_csv_text().encode("cp1251"))

    table = read_csv(path)

    assert _as_tuples(table)[1][3] == "Бейшпиль ГмбХ"


def test_utf8_wins_over_detector() -> None:
    """B3: UTF-8 проверяется первым и строго — успех есть доказательство, а не вероятность.

    На коротком тексте `chardet` уверенно предлагает `windows-1252`; если бы его
    подсказка шла раньше, кириллица в UTF-8-файле портилась бы именно на
    маленьких списках — тех, что грузят руками.
    """
    assert decode("домен,клиент\nexample.com,Ромашка\n".encode()).startswith("домен")


def test_xlsx_dates_and_numbers_are_strings(tmp_path: Path) -> None:
    """B2: Excel хранит дату числом, а объём работ — float, наружу идут строки.

    Иначе `120.0` и `2025-01-01 00:00:00` попали бы в правила и в отчёт.
    """
    from datetime import date

    path = tmp_path / "typed.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["domain", "period_start", "work_volume"])
    sheet.append(["example.com", date(2025, 1, 1), 120.0])
    workbook.save(path)

    row = read_xlsx(path).data_rows()[0]

    assert row.get("period_start") == "2025-01-01"
    assert row.get("work_volume") == "120"


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        (
            "https://docs.google.com/spreadsheets/d/abc123/edit#gid=42",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=42",
        ),
        (
            "https://docs.google.com/spreadsheets/d/abc123/edit?usp=sharing",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=0",
        ),
        (
            "https://docs.google.com/spreadsheets/d/abc123/edit?gid=7#gid=7",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=7",
        ),
    ],
)
def test_sheet_link_to_export_url(link: str, expected: str) -> None:
    """B2: ссылку присылают в четырёх формах, экспорт из них один."""
    assert sheet_export_url(link) == expected


def test_sheet_link_must_look_like_sheet() -> None:
    """B16: не ссылка на таблицу — внятный отказ, а не попытка её скачать."""
    with pytest.raises(SheetLinkError):
        sheet_export_url("https://example.com/list.csv")


def test_private_sheet_is_an_error_not_an_empty_list() -> None:
    """B16: закрытая таблица отдаёт страницу входа со статусом 200.

    Без этой проверки приём отчитался бы «принято 0, отклонено 0» — соврал бы
    успехом там, где список просто не прочитан.
    """
    with pytest.raises(SheetAccessError):
        read_gsheet(
            "https://docs.google.com/spreadsheets/d/abc123/edit",
            fetch=lambda _url: b"<!DOCTYPE html><html><body>Sign in</body></html>",
        )
