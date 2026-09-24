"""Подсказки экрана о списке говорят то же, что требует приём. Пример приёмки V19.

Описание колонок живёт на фронте (`web/src/pages/intake/listFormat.json`) —
там же, где его читают обе подсказки, у файла и у ссылки. Требования живут на
сервере. Разойдись они — человек соберёт таблицу по нашей же неверной
подсказке и получит отказ, которого подсказка не предвещала.

Тест читает **оба настоящих места** (урок L123), а не копию списка: копия
расходится с настоящим ровно тогда, ради чего написана, — когда появится новая
колонка.
"""

from __future__ import annotations

import json
from pathlib import Path

from ahrefs_cases.api.routers.intake import MAX_UPLOAD_BYTES
from ahrefs_cases.intake.accept import FILE_SUFFIXES
from ahrefs_cases.intake.validate import MAY_BE_EMPTY, OPTIONAL_COLUMNS, REQUIRED_COLUMNS

_FORMAT = Path(__file__).resolve().parents[1] / "web/src/pages/intake/listFormat.json"
_MEGABYTE = 1024 * 1024


def _help() -> dict[str, object]:
    data = json.loads(_FORMAT.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _columns(key: str = "columns") -> list[dict[str, object]]:
    columns = _help()[key]
    assert isinstance(columns, list)
    return columns


def test_help_names_exactly_the_required_columns_in_order() -> None:
    """V19: обязательные колонки подсказки — те же и в том же порядке, что у приёма.

    Порядок тоже договор: по подсказке собирают шапку, и таблица, собранная
    слева направо по ней, должна совпадать с тем, что перечисляет отказ.
    """
    assert [column["name"] for column in _columns()] == list(REQUIRED_COLUMNS)


def test_help_names_the_optional_columns_and_the_one_that_may_be_empty() -> None:
    """V19: необязательные колонки и «можно оставить пустым» — как на сервере."""
    may_be_empty = {column["name"] for column in _columns() if column.get("mayBeEmpty")}

    assert [column["name"] for column in _columns("optional")] == list(OPTIONAL_COLUMNS)
    assert may_be_empty == set(MAY_BE_EMPTY)


def test_every_column_is_described() -> None:
    """V19: у каждой колонки есть «что это», у обязательной — ещё и пример.

    Пустая строка в подсказке не помогает: по ней таблицу не соберёшь.
    """
    for column in _columns():
        assert column.get("what"), column
        assert column.get("example"), column
    for column in _columns("optional"):
        assert column.get("what"), column


def test_help_names_the_file_formats_and_the_size_limit_the_server_takes() -> None:
    """V19: форматы и предел файла в подсказке — те, что принимает сервер.

    Из тех же данных строится фильтр выбора файла, поэтому расхождение здесь —
    это ещё и диалог, который прячет годный файл или предлагает негодный.
    """
    help_data = _help()

    assert help_data["fileSuffixes"] == list(FILE_SUFFIXES)
    assert help_data["maxMegabytes"] == MAX_UPLOAD_BYTES / _MEGABYTE
