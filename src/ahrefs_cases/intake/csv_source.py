"""Чтение списка проектов из CSV. Кодировка и разделитель определяются, не задаются.

Список приходит выгрузкой из Excel, а Excel в русской локали сохраняет CSV в
cp1251 и с точкой с запятой. Требовать от отдела «сохраните в UTF-8 с запятыми»
значит получать испорченные файлы и разбираться с ними вручную каждый раз.

Определение кодировки — цепочка, а не единственная догадка `chardet`: на файле в
двадцать строк он ошибается уверенно, и его ответ проверяется попыткой разбора.
"""

from __future__ import annotations

import csv
from pathlib import Path

import chardet

from ahrefs_cases.intake.rejections import UnfitSourceError
from ahrefs_cases.intake.rows import RawTable, table_from_matrix

_FALLBACK_ENCODINGS = ("utf-8-sig", "cp1251", "latin-1")
"""Порядок значим. `latin-1` последний и декодирует что угодно: он существует,
чтобы файл вообще открылся, а не чтобы текст был верным."""

_DETECT_CONFIDENCE = 0.8
_DELIMITERS = ",;\t"
_SNIFF_BYTES = 8192
_BINARY_PROBE = 4096
"""Сколько символов начала смотреть в поисках нулевого байта. В тексте его не
бывает (UTF-16 с меткой порядка байт — выгрузка Excel «Юникод» — раскодирован
раньше и нулей уже не содержит), а в книге Excel и в PDF он стоит в первых
сотнях байт."""


def read_csv(path: Path) -> RawTable:
    """CSV → сырая таблица. Кодировка и разделитель определяются по содержимому."""
    return parse_csv_text(decode(path.read_bytes()), origin=str(path))


def parse_csv_text(text: str, origin: str, where: str = "") -> RawTable:
    """Текст CSV → сырая таблица. Один разбор на файл и на Google Sheet.

    Экспорт таблицы — тот же CSV, и разбирать его вторым способом («поделить по
    запятой») значило бы получить разное поведение на кавычках и на заметке с
    запятой внутри — ровно там, где расхождение заметят не сразу.

    Двоичный файл под именем `.csv` (книга Excel, PDF) раскодируется всегда —
    `latin-1` читает любые байты, — и без проверки его мусор становился шапкой,
    а ответ — «Принято». Длинная строка без переводов роняла модуль `csv`
    (`field larger than field limit`), и человек получал пятисотку.
    """
    if "\x00" in text[:_BINARY_PROBE]:
        raise UnfitSourceError(
            "не похож на текст — это двоичный файл с расширением .csv (книга Excel, PDF "
            "или что-то ещё). Сохраните список как CSV или XLSX."
        )
    delimiter = _sniff_delimiter(text)
    try:
        matrix = list(csv.reader(text.splitlines(), delimiter=delimiter))
    except csv.Error as exc:
        raise UnfitSourceError(
            f"не читается как CSV ({exc}): похоже, это не текстовая таблица. "
            "Сохраните список как CSV или XLSX."
        ) from exc
    return table_from_matrix(origin, matrix, where=where)


def decode(data: bytes) -> str:
    """Байты → текст. Сначала UTF-8, затем подсказка `chardet`, затем цепочка.

    UTF-8 проверяется первым и строго: он либо разбирается целиком, либо не
    разбирается вовсе — то есть его успех является доказательством, а не
    вероятностью. Так частый случай не зависит от эвристики.
    """
    if not data:
        return ""

    for encoding in ("utf-8-sig", "utf-8"):
        decoded = _try_decode(data, encoding)
        if decoded is not None:
            return decoded

    guess = chardet.detect(data)
    guessed_encoding = guess.get("encoding")
    confidence = guess.get("confidence") or 0.0
    if guessed_encoding and confidence >= _DETECT_CONFIDENCE:
        decoded = _try_decode(data, guessed_encoding)
        if decoded is not None:
            return decoded

    for encoding in _FALLBACK_ENCODINGS:
        decoded = _try_decode(data, encoding)
        if decoded is not None:
            return decoded

    return data.decode("latin-1", errors="replace")


def _try_decode(data: bytes, encoding: str) -> str | None:
    try:
        return data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return None


def _sniff_delimiter(text: str) -> str:
    """Разделитель по первой строке: `,`, `;` или таб.

    `csv.Sniffer` здесь не используется: на файле с одной колонкой и запятыми
    внутри значения он выбирает разделителем запятую внутри текста заметки.
    Заголовок для этого надёжнее — в нём кавычек и заметок не бывает.
    """
    header = text.splitlines()[0] if text else ""
    counts = {delimiter: header.count(delimiter) for delimiter in _DELIMITERS}
    best = max(counts, key=lambda delimiter: counts[delimiter])
    return best if counts[best] else ","
