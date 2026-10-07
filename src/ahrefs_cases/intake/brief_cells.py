"""Колонки брифа во входном файле: заполнить бриф пачкой, а не по карточке.

Какие поля брифа приходят колонками, решает их описание (`storage.brief`,
поле `column`), а не этот модуль: колонка без поля или поле без разбора здесь
появиться не может.

Ячейка брифа — сведения, которые **разрешено не знать** (урок L67): непонятая
ячейка — замечание, а не отказ строки, и записывается только то, что понято.
Пустая ячейка значит «нет сведений», а не «очистить»: повторная загрузка того же
списка не стирает того, что специалист дописал в карточке.
"""

from __future__ import annotations

from types import MappingProxyType

from ahrefs_cases.intake.rejections import Notice, RejectReason
from ahrefs_cases.intake.rows import RawRow
from ahrefs_cases.storage.brief import FIELDS, BriefRejected, FieldKind, normalize

COLUMN_FIELDS = tuple(field for field in FIELDS if field.column)
BRIEF_COLUMNS = tuple(field.column for field in COLUMN_FIELDS)
"""Колонки брифа в порядке шаблона — в нём их перечисляет подсказка экрана."""

_REASON = MappingProxyType(
    {
        FieldKind.CHOICE: RejectReason.BAD_ENUM,
        FieldKind.LINK: RejectReason.BAD_LINK,
        FieldKind.TEXT: RejectReason.TOO_LONG,
        FieldKind.LONG_TEXT: RejectReason.TOO_LONG,
    }
)
_SHOWN = 60


def parse_brief(row: RawRow, notices: list[Notice]) -> dict[str, str]:
    """Колонки брифа строки → поля брифа; непонятое — в замечания, строка принята."""
    brief: dict[str, str] = {}
    for field in COLUMN_FIELDS:
        raw = row.get(field.column)
        if not raw:
            continue
        value = normalize(field, raw)
        if isinstance(value, BriefRejected):
            notices.append(
                Notice(row.row_no, field.column, _REASON[field.kind], _detail(raw, value))
            )
            continue
        brief[field.key] = value
    return brief


def _detail(raw: str, rejected: BriefRejected) -> str:
    """Что не понято — с началом ячейки, если отказ её не называет сам (пункт списка называет)."""
    if raw in rejected.detail:
        return rejected.detail
    shown = raw if len(raw) <= _SHOWN else f"{raw[:_SHOWN]}…"
    return f"«{shown}»: {rejected.detail}"
