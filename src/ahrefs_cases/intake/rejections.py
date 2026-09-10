"""Коды отказа при приёме списка. Строка не проходит — прогон продолжается.

Требование ТЗ прямое: битая строка не останавливает загрузку остальных. Значит
отказ обязан быть **данными** (код + поле + строка источника), а не исключением:
исключение прерывает разбор, а его текст невозможно показать на экране Ф6 иначе
как строкой лога.

Коды — часть контракта с фронтом: экран группирует отказы по `reason`, поэтому
новый код добавляется здесь, а не собирается из f-строк по месту.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RejectReason(StrEnum):
    """Почему строка не стала проектом."""

    EMPTY_DOMAIN = "empty_domain"
    INVALID_DOMAIN = "invalid_domain"
    IP_ADDRESS = "ip_address"
    """IP вместо домена: Ahrefs считает по хосту, и такой «проект» не соберётся."""

    EMPTY_SOURCE = "empty_source"
    """Источник прочитан, но в нём нет ни одной колонки: пустой файл, не тот лист,
    выгрузка без заголовка. Один отказ на файл, а не десять «нет колонки»."""

    MISSING_FIELD = "missing_field"
    MISSING_COLUMN = "missing_column"
    """Нет самой колонки — брак не строки, а файла: отчёт скажет это один раз."""

    BAD_DATE = "bad_date"
    PERIOD_ORDER = "period_order"
    BAD_GEO = "bad_geo"
    BAD_ENUM = "bad_enum"
    BAD_NUMBER = "bad_number"
    BAD_FLAG = "bad_flag"
    DUPLICATE_IN_SOURCE = "duplicate_in_source"
    """Домен встречается в файле дважды. Побеждает последняя строка, но обе
    попадают в отчёт: тихое схлопывание скрыло бы ошибку в самом списке."""


@dataclass(frozen=True, slots=True)
class Rejection:
    """Отказ по конкретной строке источника.

    `row_no` — номер строки **в источнике**, включая заголовок, а не индекс в
    массиве: человек будет искать её глазами в Excel, и off-by-one здесь стоит
    ему минуты на каждой строке.
    """

    row_no: int
    field: str
    reason: RejectReason
    detail: str = ""
