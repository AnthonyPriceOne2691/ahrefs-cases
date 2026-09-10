"""Приём списка проектов: CSV/XLSX → валидированные Project-записи.

Ф1. Темы модулей:
- `csv_source.py`   — чтение CSV с fallback-цепочкой кодировок (utf-8-sig → utf-8 → cp1251 → latin-1)
- `normalize.py`    — домен → канонический хост (схема/www/punycode/путь срезаются)
- `validate.py`     — обязательность period_start, границы периода, ISO-код гео
"""
