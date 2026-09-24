"""Правила приёма: сырая строка → черновик проекта или отказы.

Обязательность колонок — таблица (`REQUIRED_COLUMNS`), приведение типов —
маленькие функции. Лестница `if` здесь выросла бы до сорока веток и стала бы
единственным местом, где правила ТЗ невозможно перечитать.

Строка собирает **все** свои отказы, а не первый: список правят в Excel руками,
и три прохода «исправил дату — узнал про гео — узнал про флаг» стоят человеку
трёх загрузок.

Граница двух браков проведена здесь же (`check_fit`): чего нет в **шапке**, того
нет ни в одной строке — это брак файла, и он отказывает целиком; чего нет в
**ячейке** — брак строки, и он попадает в отчёт, не мешая соседям.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from ahrefs_cases.intake.drafts import ProjectDraft
from ahrefs_cases.intake.normalize import DomainRejected, normalize_domain
from ahrefs_cases.intake.rejections import Notice, Rejection, RejectReason, UnfitSourceError
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
MAY_BE_EMPTY = frozenset({"work_volume"})
"""Обязательная колонка, ячейки которой разрешено оставлять пустыми. Открыто
наружу: подсказка экрана говорит то же самое, и тест сверяет их (V19)."""

_KNOWN_COLUMNS = frozenset(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
_EXPECTED = (
    f"Нужна шапка в первой строке с колонками {', '.join(REQUIRED_COLUMNS)} "
    f"(необязательные: {', '.join(OPTIONAL_COLUMNS)}) — имена латиницей."
)
_BLANK_HEADER = "первая строка пуста — шапка должна стоять в первой строке."
_SEEN_CELLS = 6
_SEEN_WIDTH = 60

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")
_GEO_RE = re.compile(r"^[A-Za-z]{2}$")
_TRUE = frozenset({"yes", "y", "true", "1", "да", "+"})
_FALSE = frozenset({"no", "n", "false", "0", "нет", "-", ""})


def validate_table(table: RawTable) -> tuple[list[ProjectDraft], list[Rejection], list[Notice]]:
    """Таблица → черновики, отказы и замечания.

    Новости три, а не две: строка принята, строка принята с непонятой ячейкой,
    строка отклонена. Дубль домена в файле отмечается, не глотается. Файл,
    который не годится целиком, до строк не доходит (`check_fit`).
    """
    check_fit(table)

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


def check_fit(table: RawTable) -> None:
    """Годится ли источник целиком. Нет — `UnfitSourceError`, и в базу не пишется ничего.

    Четыре брака файла: строк нет вовсе, нет обязательных колонок, колонка из
    известных стоит в шапке дважды (какую читать — неизвестно; раньше молча
    бралась последняя), только шапка. Беды шапки называются **разом**, как
    отказы строки: два прохода «поправил имя — узнал про дубль» стоят человеку
    двух загрузок. Текст называет прочитанное и ожидаемое, потому что человек
    чинит файл по нему, а не по коду ответа.
    """
    if not table.columns:
        # Пустая первая строка над списком выглядит так же, как пустой файл:
        # `csv` отдаёт её пустым списком. Различают их строки ниже неё.
        if table.rows:
            raise UnfitSourceError(_sentences([_BLANK_HEADER, _EXPECTED]))
        raise UnfitSourceError(_sentences(["нет ни одной строки.", table.where, _EXPECTED]))
    counts = Counter(table.columns)
    doubled = sorted(name for name in _KNOWN_COLUMNS if counts[name] > 1)
    missing = missing_columns(table)
    if missing or doubled:
        raise UnfitSourceError(
            _sentences(
                [
                    _missing_text(table, missing) if missing else "",
                    f"в шапке дважды: {', '.join(doubled)} — непонятно, какую колонку "
                    "читать, оставьте по одной."
                    if doubled
                    else "",
                    _EXPECTED if missing else "",
                ]
            )
        )
    if not table.data_rows():
        raise UnfitSourceError(
            "только шапка — строк со списком нет. Проекты идут со второй строки, по одному "
            "на строку."
        )


def _missing_text(table: RawTable, missing: tuple[str, ...]) -> str:
    """Чего нет, на что похоже имеющееся, что прочитано и что ожидается.

    Прочитанное показывается, только когда не нашлось **ни одной** нужной
    колонки: так выглядят шапка по-русски, чужой разделитель («domain|…» одной
    ячейкой), список на другом листе. Когда не хватает двух колонок из десяти,
    перечень восьми правильных — шум.
    """
    if len(missing) == len(REQUIRED_COLUMNS):
        # Все десять перечислены в ожидаемом ниже — второй раз подряд это шум.
        parts = ["нет ни одной нужной колонки.", _seen(table.columns), table.where]
    else:
        word = "колонки" if len(missing) == 1 else "колонок"
        parts = [f"нет {word} {', '.join(missing)}.", _near_names(table.columns, missing)]
    return _sentences(parts)


def _sentences(parts: list[str]) -> str:
    """Предложения через пробел, каждое следующее — с заглавной; пустые пропускаются.

    Первое остаётся строчным: перед ним встанет «Файл «x» не подходит:».
    """
    kept = [part for part in parts if part]
    return " ".join(part if i == 0 else part[:1].upper() + part[1:] for i, part in enumerate(kept))


def _near_names(columns: tuple[str, ...], missing: tuple[str, ...]) -> str:
    """Подсказка для имени, отличающегося от нужного только пробелами и знаками.

    Регистр приём прощает (`Domain` — это `domain`), и человек ждёт, что простит
    и `Period Start`. Не прощает: принять значило бы расширить формат, а не
    проверить его, — и второе правило соответствия имён (урок L124). Поэтому
    похожесть считается **только для текста**; сличение шапки по-прежнему одно,
    в `rows.normalize_columns`.
    """
    squashed = {_squash(name): name for name in columns if name and name not in _KNOWN_COLUMNS}
    hints = [
        f"{name} — в шапке «{squashed[_squash(name)]}», переименуйте"
        for name in missing
        if _squash(name) in squashed
    ]
    return f"Похоже на опечатку: {'; '.join(hints)}." if hints else ""


def _squash(name: str) -> str:
    return re.sub(r"[\W_]+", "", name)


def _seen(columns: tuple[str, ...]) -> str:
    """Что стоит в первой строке — как прочитано, первые несколько ячеек."""
    cells = [name for name in columns if name]
    if not cells:
        return _BLANK_HEADER
    shown = ", ".join(f"«{_clip(name)}»" for name in cells[:_SEEN_CELLS])
    rest = len(cells) - _SEEN_CELLS
    more = f" и ещё {rest}" if rest > 0 else ""
    seen = f"В первой строке сейчас: {shown}{more}."
    # Одна ячейка, в которой стоят сразу несколько нужных имён, — шапка не
    # разделилась: разделитель не тот, что мы ищем (`csv_source._DELIMITERS`).
    if len(cells) == 1 and sum(name in cells[0] for name in REQUIRED_COLUMNS) > 1:
        seen += (
            " Шапка не разделилась на колонки: разделитель — запятая, точка с запятой"
            " или табуляция."
        )
    return seen


def _clip(name: str) -> str:
    return name if len(name) <= _SEEN_WIDTH else f"{name[:_SEEN_WIDTH]}…"


def validate_row(row: RawRow) -> tuple[ProjectDraft | None, list[Rejection], list[Notice]]:
    """Строка → черновик, её отказы (все сразу) и замечания к принятой строке."""
    rejections = [
        Rejection(row_no=row.row_no, field=column, reason=RejectReason.MISSING_FIELD)
        for column in REQUIRED_COLUMNS
        if column not in MAY_BE_EMPTY and not row.get(column)
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
