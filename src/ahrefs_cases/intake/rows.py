"""Сырая таблица входа: один формат для CSV, XLSX и Google Sheet.

Три источника сводятся к одному типу до всякой проверки. Иначе валидация,
нормализация и отчёт существовали бы в трёх похожих экземплярах, и требование
«источник не влияет на результат» (пример B2) проверялось бы тремя тестами
вместо одного, а расходились бы они молча.

Значения — строки. Приведение типов (даты, числа, флаги) живёт в `validate.py`:
XLSX отдал бы `datetime`, CSV — строку, и разница просочилась бы в правила.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

_HEADER_ROW_NO = 1


@dataclass(frozen=True, slots=True)
class RawRow:
    """Строка источника с её номером — тем, который человек видит в Excel.

    Нумерация с единицы и включает заголовок: отчёт «строка 47» должен
    приводить к той самой строке, а не к соседней.
    """

    row_no: int
    values: Mapping[str, str]

    def get(self, column: str) -> str:
        """Значение колонки без окружающих пробелов; нет колонки — пустая строка.

        Отсутствие колонки не ошибка этого уровня: её ловит `validate.py` один
        раз на таблицу (`MISSING_COLUMN`), а не по разу на каждой из ста строк.
        """
        return self.values.get(column, "").strip()

    def is_blank(self) -> bool:
        """Пустая строка в конце выгрузки — не брак, а хвост файла.

        Excel охотно отдаёт сотню пустых строк после данных. Считать их
        отклонёнными значило бы утопить настоящие семь отказов в отчёте.
        """
        return not any(value.strip() for value in self.values.values())


@dataclass(frozen=True, slots=True)
class RawTable:
    """Прочитанный источник целиком.

    `origin` — что именно читали (путь файла или ссылка): в отчёте о приёме без
    этого не отличить два одинаковых списка из разных отделов.
    """

    origin: str
    columns: tuple[str, ...]
    rows: tuple[RawRow, ...]

    def data_rows(self) -> tuple[RawRow, ...]:
        return tuple(row for row in self.rows if not row.is_blank())


def build_rows(columns: tuple[str, ...], values: list[list[str]]) -> tuple[RawRow, ...]:
    """Матрица значений → строки с номерами, начиная со второй (первая — заголовок).

    Короткая строка (Excel обрезает хвостовые пустые ячейки) дополняется пустыми
    значениями: иначе `dict(zip(...))` тихо потерял бы последние колонки, и
    «нет значения» стало бы неотличимо от «нет колонки».
    """
    rows: list[RawRow] = []
    for offset, raw_values in enumerate(values, start=_HEADER_ROW_NO + 1):
        padded = list(raw_values) + [""] * (len(columns) - len(raw_values))
        rows.append(RawRow(row_no=offset, values=dict(zip(columns, padded, strict=False))))
    return tuple(rows)


def normalize_columns(header: list[str]) -> tuple[str, ...]:
    """Заголовки к нижнему регистру без пробелов по краям.

    `Domain `, `DOMAIN` и `domain` — одна колонка: список правят руками в Excel,
    и требовать точного регистра значило бы браковать файл целиком из-за формы
    заголовка.
    """
    return tuple(column.strip().lower() for column in header)
