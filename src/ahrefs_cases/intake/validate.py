"""Правила приёма: сырая строка → черновик проекта или отказы.

Обязательность колонок — таблица (`REQUIRED_COLUMNS`), приведение типов —
маленькие функции. Лестница `if` здесь выросла бы до сорока веток и стала бы
единственным местом, где правила ТЗ невозможно перечитать.

Строка собирает **все** свои отказы, а не первый: список правят в Excel руками,
и три прохода «исправил дату — узнал про гео — узнал про флаг» стоят человеку
трёх загрузок.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ahrefs_cases.intake.drafts import ProjectDraft
from ahrefs_cases.intake.normalize import DomainRejected, normalize_domain
from ahrefs_cases.intake.rejections import Notice, Rejection, RejectReason
from ahrefs_cases.intake.rows import RawRow, RawTable
from ahrefs_cases.storage._enums import TargetMode

REQUIRED_COLUMNS = (
    "domain",
    "period_start",
    "period_end",
    "niche",
    "geo",
    "service_type",
    "work_volume",
    "client",
    "owner",
    "publishable",
)
"""Десять полей §4. `work_volume` в списке обязательных **колонок**, но его
значение может быть пустым: ТЗ требует его спрашивать, а модель Ф1 разрешает не
знать (тогда блок «что сделали» в кейсе скрывается, а не выдумывается)."""

OPTIONAL_COLUMNS = ("target_mode", "notes")
_MAY_BE_EMPTY = frozenset({"work_volume"})

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")
_GEO_RE = re.compile(r"^[A-Za-z]{2}$")
_TRUE = frozenset({"yes", "y", "true", "1", "да", "+"})
_FALSE = frozenset({"no", "n", "false", "0", "нет", "-", ""})


def validate_table(table: RawTable) -> tuple[list[ProjectDraft], list[Rejection], list[Notice]]:
    """Таблица → черновики, отказы и замечания.

    Новости три, а не две: строка принята, строка принята с непонятой ячейкой,
    строка отклонена. Дубль домена в файле отмечается, не глотается.
    """
    if not table.columns:
        return (
            [],
            [
                Rejection(
                    row_no=1,
                    field="*",
                    reason=RejectReason.EMPTY_SOURCE,
                    detail=table.origin,
                )
            ],
            [],
        )

    missing = missing_columns(table)
    if missing:
        return (
            [],
            [
                Rejection(row_no=1, field=column, reason=RejectReason.MISSING_COLUMN)
                for column in missing
            ],
            [],
        )

    drafts: dict[tuple[str, TargetMode, date], ProjectDraft] = {}
    rejections: list[Rejection] = []
    notices: list[Notice] = []
    for row in table.data_rows():
        draft, row_rejections, row_notices = validate_row(row)
        rejections.extend(row_rejections)
        if draft is None:
            # Замечания отклонённой строки не показываем: строки нет, и
            # говорить о её ячейке значит предлагать чинить то, что не спасёт.
            continue
        notices.extend(row_notices)
        if draft.key in drafts:
            rejections.append(
                Rejection(
                    row_no=drafts[draft.key].row_no,
                    field="domain",
                    reason=RejectReason.DUPLICATE_IN_SOURCE,
                    detail=f"перекрыта строкой {draft.row_no}",
                )
            )
        drafts[draft.key] = draft
    return list(drafts.values()), rejections, notices


def missing_columns(table: RawTable) -> tuple[str, ...]:
    """Колонки, которых нет в файле. Брак файла, а не строк — сообщается один раз."""
    present = set(table.columns)
    return tuple(column for column in REQUIRED_COLUMNS if column not in present)


def validate_row(row: RawRow) -> tuple[ProjectDraft | None, list[Rejection], list[Notice]]:
    """Строка → черновик, её отказы (все сразу) и замечания к принятой строке."""
    rejections = [
        Rejection(row_no=row.row_no, field=column, reason=RejectReason.MISSING_FIELD)
        for column in REQUIRED_COLUMNS
        if column not in _MAY_BE_EMPTY and not row.get(column)
    ]
    notices: list[Notice] = []

    domain = _parse_domain(row, rejections)
    period = _parse_period(row, rejections)
    target_mode = _parse_target_mode(row, rejections)
    publishable = _parse_flag(row, rejections)
    work_volume = _parse_volume(row, notices)
    geo = _parse_geo(row, rejections)

    if rejections or domain is None or period is None or target_mode is None:
        return None, rejections, notices

    return (
        ProjectDraft(
            row_no=row.row_no,
            domain=domain,
            target_mode=target_mode,
            period_start=period[0],
            period_end=period[1],
            niche=row.get("niche"),
            geo=geo,
            service_type=row.get("service_type"),
            client=row.get("client"),
            owner=row.get("owner"),
            publishable=bool(publishable),
            work_volume=work_volume,
            notes=row.get("notes"),
        ),
        [],
        notices,
    )


def _parse_domain(row: RawRow, rejections: list[Rejection]) -> str | None:
    raw = row.get("domain")
    if not raw:
        return None
    result = normalize_domain(raw)
    if isinstance(result, DomainRejected):
        rejections.append(
            Rejection(row.row_no, "domain", result.reason, result.detail or raw),
        )
        return None
    return result


def _parse_period(row: RawRow, rejections: list[Rejection]) -> tuple[date, date] | None:
    start = _parse_date(row, "period_start", rejections)
    end = _parse_date(row, "period_end", rejections)
    if start is None or end is None:
        return None
    if end < start:
        rejections.append(
            Rejection(
                row.row_no,
                "period_end",
                RejectReason.PERIOD_ORDER,
                f"{end.isoformat()} раньше {start.isoformat()}",
            )
        )
        return None
    return start, end


def _parse_date(row: RawRow, column: str, rejections: list[Rejection]) -> date | None:
    raw = row.get(column)
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()  # noqa: DTZ007 — календарная дата, не момент
        except ValueError:
            continue
    rejections.append(Rejection(row.row_no, column, RejectReason.BAD_DATE, raw))
    return None


def _parse_geo(row: RawRow, rejections: list[Rejection]) -> str:
    """ISO 3166-1 alpha-2 проверяется формой, а не справочником.

    Полный справочник — отдельная зависимость ради двухбуквенного кода; ошибку
    вида `Германия` форма ловит, а выдуманный, но правдоподобный `XZ` поймает
    Ahrefs пустой историей — с пометкой в `RunItem`, а не потерей строки.
    """
    raw = row.get("geo")
    if raw and not _GEO_RE.match(raw):
        rejections.append(Rejection(row.row_no, "geo", RejectReason.BAD_GEO, raw))
        return ""
    return raw.upper()


def _parse_target_mode(row: RawRow, rejections: list[Rejection]) -> TargetMode | None:
    raw = row.get("target_mode")
    if not raw:
        return TargetMode.SUBDOMAINS
    try:
        return TargetMode(raw.lower())
    except ValueError:
        rejections.append(Rejection(row.row_no, "target_mode", RejectReason.BAD_ENUM, raw))
        return None


def _parse_flag(row: RawRow, rejections: list[Rejection]) -> bool | None:
    raw = row.get("publishable").lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    rejections.append(Rejection(row.row_no, "publishable", RejectReason.BAD_FLAG, raw))
    return None


def _parse_volume(row: RawRow, notices: list[Notice]) -> int | None:
    """Объём работ числом. Не разобрали — **замечание, а не отказ строки**.

    Колонку заполняют руками и словами: «214 ссылок», «за 18 месяцев 132
    ссылки». Пустая ячейка здесь законна, значит непонятая обязана стоить не
    дороже пустой — иначе строка с меньшей информацией принимается, а с
    большей отклоняется. Число при этом не выдумывается: «12 статей и 214
    ссылок» дало бы 12, и оно молча уехало бы в кейс клиенту.
    """
    raw = row.get("work_volume")
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        notices.append(Notice(row.row_no, "work_volume", RejectReason.BAD_NUMBER, raw))
        return None
