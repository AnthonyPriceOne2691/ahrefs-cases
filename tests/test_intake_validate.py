"""Правила приёма построчно: какие значения проходят и какой код получает брак.

Дополняет B1 (там проверялся счёт по файлу целиком) разбором отдельных правил.
Коды отказа — часть контракта с экраном Ф6: он группирует отказы по `reason`,
поэтому проверяется именно код, а не текст сообщения.
"""

from __future__ import annotations

from datetime import date

import pytest

from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.intake.drafts import ProjectDraft
from ahrefs_cases.intake.rejections import Rejection, RejectReason
from ahrefs_cases.intake.report import IntakeReport
from ahrefs_cases.intake.validate import validate_table
from ahrefs_cases.storage._enums import TargetMode

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
BASE = "ok.example.com,2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"


def _validate(row: str) -> tuple[list[ProjectDraft], list[Rejection]]:
    table = parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test")
    return validate_table(table)


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (BASE.replace(",2025-01-01,", ",01-2025-01,"), RejectReason.BAD_DATE),
        (BASE.replace(",subdomains,", ",поддомены,"), RejectReason.BAD_ENUM),
        (BASE.replace(",10,Acme", ",много,Acme"), RejectReason.BAD_NUMBER),
        (BASE.replace(",yes,", ",может быть,"), RejectReason.BAD_FLAG),
        (BASE.replace(",fintech,", ",,"), RejectReason.MISSING_FIELD),
    ],
)
def test_bad_value_gets_its_code(row: str, reason: RejectReason) -> None:
    """Каждое правило отвечает своим кодом, а не общим «строка плохая»."""
    drafts, rejections = _validate(row)

    assert not drafts
    assert reason in {item.reason for item in rejections}


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("2025-01-01", date(2025, 1, 1)),
        ("01.01.2025", date(2025, 1, 1)),
        ("01/01/2025", date(2025, 1, 1)),
        ("2025/01/01", date(2025, 1, 1)),
    ],
)
def test_date_formats_people_actually_type(written: str, expected: date) -> None:
    """Список правят в Excel руками, и дата приходит в четырёх видах.

    Требовать ISO значило бы браковать половину файла из-за региональных
    настроек Excel — то есть возвращать список отделу вместо приёма.
    """
    drafts, rejections = _validate(BASE.replace("2025-01-01", written))

    assert not rejections
    assert drafts[0].period_start == expected


@pytest.mark.parametrize("flag", ["yes", "да", "1", "true", "+"])
def test_publishable_true_forms(flag: str) -> None:
    """«Можно публиковать» пишут пятью способами, и все они означают одно."""
    drafts, _ = _validate(BASE.replace(",yes,", f",{flag},"))

    assert drafts[0].publishable is True


@pytest.mark.parametrize("flag", ["no", "нет", "0", "false", "-"])
def test_publishable_false_forms(flag: str) -> None:
    drafts, _ = _validate(BASE.replace(",yes,", f",{flag},"))

    assert drafts[0].publishable is False


def test_empty_work_volume_is_allowed() -> None:
    """Единственное поле из десяти, значение которого может быть пустым.

    ТЗ требует спрашивать объём работ, модель Ф1 разрешает его не знать: тогда
    блок «что сделали» в кейсе скрывается, а не выдумывается.
    """
    drafts, rejections = _validate(BASE.replace(",10,Acme", ",,Acme"))

    assert not rejections
    assert drafts[0].work_volume is None


def test_default_target_mode_is_subdomains() -> None:
    """Пустой `target_mode` — не брак: по умолчанию считаем поддомены."""
    drafts, rejections = _validate(BASE.replace(",subdomains,", ",,"))

    assert not rejections
    assert drafts[0].target_mode is TargetMode.SUBDOMAINS


def test_row_collects_all_its_reasons() -> None:
    """Три ошибки в строке — три причины сразу, а не три загрузки файла подряд."""
    row = (
        BASE.replace(",2025-01-01,", ",вчера,")
        .replace(",US,", ",Германия,")
        .replace(",yes,", ",ага,")
    )

    _drafts, rejections = _validate(row)

    reasons = {item.reason for item in rejections}
    assert reasons == {RejectReason.BAD_DATE, RejectReason.BAD_GEO, RejectReason.BAD_FLAG}


def test_geo_is_upper_cased() -> None:
    """`us` и `US` — одна страна: гео уходит в базу в каноничном виде."""
    drafts, _ = _validate(BASE.replace(",US,", ",us,"))

    assert drafts[0].geo == "US"


def test_report_lines_name_row_and_reason() -> None:
    """Текст отчёта для CLI называет строку и причину — по ней и ищут в Excel."""
    _drafts, rejections = _validate(BASE.replace(",yes,", ",ага,"))
    report = IntakeReport(origin="list.csv", accepted=0, rejections=tuple(rejections))

    lines = report.as_lines()

    assert "источник: list.csv" in lines[0]
    assert "строка 2" in lines[-1]
    assert RejectReason.BAD_FLAG.value in lines[-1]


def test_empty_file_is_one_rejection_not_ten() -> None:
    """Пустой файл — один отказ «источник пуст», а не десять «нет колонки».

    Десять одинаковых строк в отчёте выглядят как десять проблем; проблема одна,
    и человек должен увидеть её одной строкой.
    """
    drafts, rejections = validate_table(parse_csv_text("", origin="empty.csv"))

    assert not drafts
    assert [item.reason for item in rejections] == [RejectReason.EMPTY_SOURCE]
