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
from ahrefs_cases.intake.rejections import Notice, Rejection, RejectReason
from ahrefs_cases.intake.report import IntakeReport
from ahrefs_cases.intake.validate import validate_table
from ahrefs_cases.storage._enums import TargetMode

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
BASE = "ok.example.com,2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"


def _validate(row: str) -> tuple[list[ProjectDraft], list[Rejection], list[Notice]]:
    table = parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test")
    return validate_table(table)


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (BASE.replace(",2025-01-01,", ",01-2025-01,"), RejectReason.BAD_DATE),
        (BASE.replace(",subdomains,", ",поддомены,"), RejectReason.BAD_ENUM),
        (BASE.replace(",yes,", ",может быть,"), RejectReason.BAD_FLAG),
        (BASE.replace(",fintech,", ",,"), RejectReason.MISSING_FIELD),
    ],
)
def test_bad_value_gets_its_code(row: str, reason: RejectReason) -> None:
    """B1: каждое правило отвечает своим кодом, а не общим «строка плохая»."""
    drafts, rejections, _notices = _validate(row)

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
    """B13: список правят в Excel руками, и дата приходит в четырёх видах.

    Требовать ISO значило бы браковать половину файла из-за региональных
    настроек Excel — то есть возвращать список отделу вместо приёма.
    """
    drafts, rejections, _notices = _validate(BASE.replace("2025-01-01", written))

    assert not rejections
    assert drafts[0].period_start == expected


@pytest.mark.parametrize("flag", ["yes", "да", "1", "true", "+"])
def test_publishable_true_forms(flag: str) -> None:
    """B14: «можно публиковать» пишут пятью способами, и все они означают одно."""
    drafts, _rejections, _notices = _validate(BASE.replace(",yes,", f",{flag},"))

    assert drafts[0].publishable is True


@pytest.mark.parametrize("flag", ["no", "нет", "0", "false", "-"])
def test_publishable_false_forms(flag: str) -> None:
    """B14: обратная сторона — пять форм отрицания."""
    drafts, _rejections, _notices = _validate(BASE.replace(",yes,", f",{flag},"))

    assert drafts[0].publishable is False


def test_empty_work_volume_is_allowed() -> None:
    """B1: единственное поле из десяти, значение которого может быть пустым.

    ТЗ требует спрашивать объём работ, модель Ф1 разрешает его не знать: тогда
    блок «что сделали» в кейсе скрывается, а не выдумывается.
    """
    drafts, rejections, _notices = _validate(BASE.replace(",10,Acme", ",,Acme"))

    assert not rejections
    assert drafts[0].work_volume is None


def test_text_volume_keeps_the_project() -> None:
    """E1: «214 ссылок» — замечание, а не отказ строки.

    Найдено прогоном живого экрана: таблица из десяти годных проектов
    отклонилась целиком, потому что объём работ написан словами. Пустая ячейка
    при этом законна — значит непонятая обязана стоить не дороже пустой, иначе
    строка с меньшей информацией принимается, а с большей отклоняется.
    """
    drafts, rejections, notices = _validate(BASE.replace(",10,Acme", ",214 ссылок,Acme"))

    assert not rejections
    assert len(drafts) == 1
    assert drafts[0].work_volume is None
    assert [(item.field, item.detail) for item in notices] == [("work_volume", "214 ссылок")]


def test_numeric_volume_has_no_notice() -> None:
    """E2: число разбирается как раньше, и замечаний за собой не тянет."""
    drafts, rejections, notices = _validate(BASE)

    assert not rejections
    assert not notices
    assert drafts[0].work_volume == 10


def test_empty_volume_has_no_notice() -> None:
    """E3: «не сказали» — не новость: замечание только про непонятое."""
    _drafts, rejections, notices = _validate(BASE.replace(",10,Acme", ",,Acme"))

    assert not rejections
    assert not notices


def test_rejection_beats_notice() -> None:
    """E5: у отклонённой строки замечаний не показываем.

    Строки нет, и говорить о её ячейке значит предлагать чинить то, что строку
    не спасёт: чинить надо домен.
    """
    drafts, rejections, notices = _validate(
        BASE.replace("ok.example.com,", ",").replace(",10,Acme", ",214 ссылок,Acme")
    )

    assert not drafts
    assert rejections
    assert not notices


def test_geo_stays_a_rejection() -> None:
    """E6: смягчение не расползается. Гео — вход стоп-листа стран, и непонятое
    гео обошло бы его; там отказ и есть защита."""
    drafts, rejections, _notices = _validate(BASE.replace(",US,", ",RUSSIA,"))

    assert not drafts
    assert RejectReason.BAD_GEO in {item.reason for item in rejections}


def test_default_target_mode_is_subdomains() -> None:
    """B1: пустой `target_mode` — не брак, по умолчанию считаем поддомены."""
    drafts, rejections, _notices = _validate(BASE.replace(",subdomains,", ",,"))

    assert not rejections
    assert drafts[0].target_mode is TargetMode.SUBDOMAINS


def test_row_collects_all_its_reasons() -> None:
    """B1: три ошибки в строке — три причины сразу, а не три загрузки файла подряд."""
    row = (
        BASE.replace(",2025-01-01,", ",вчера,")
        .replace(",US,", ",Германия,")
        .replace(",yes,", ",ага,")
    )

    _drafts, rejections, _notices = _validate(row)

    reasons = {item.reason for item in rejections}
    assert reasons == {RejectReason.BAD_DATE, RejectReason.BAD_GEO, RejectReason.BAD_FLAG}


def test_geo_is_upper_cased() -> None:
    """B1: `us` и `US` — одна страна, гео уходит в базу в каноничном виде."""
    drafts, _rejections, _notices = _validate(BASE.replace(",US,", ",us,"))

    assert drafts[0].geo == "US"


def test_report_lines_name_row_and_reason() -> None:
    """B1: текст отчёта называет строку и причину — по ней и ищут в Excel."""
    _drafts, rejections, _notices = _validate(BASE.replace(",yes,", ",ага,"))
    report = IntakeReport(origin="list.csv", accepted=0, rejections=tuple(rejections))

    lines = report.as_lines()

    assert "источник: list.csv" in lines[0]
    assert "строка 2" in lines[-1]
    assert RejectReason.BAD_FLAG.value in lines[-1]


def test_empty_file_is_one_rejection_not_ten() -> None:
    """B15: пустой файл — один отказ «источник пуст», а не десять «нет колонки».

    Десять одинаковых строк в отчёте выглядят как десять проблем; проблема одна,
    и человек должен увидеть её одной строкой.
    """
    drafts, rejections, _notices = validate_table(parse_csv_text("", origin="empty.csv"))

    assert not drafts
    assert [item.reason for item in rejections] == [RejectReason.EMPTY_SOURCE]
