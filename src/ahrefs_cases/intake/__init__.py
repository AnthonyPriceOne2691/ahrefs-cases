"""Приём списка проектов: CSV/XLSX → валидированные Project-записи.

Ф1. Темы модулей:
- `csv_source.py`   — чтение XLSX и Google Sheet; для CSV fallback-цепочка кодировок
- `normalize.py`    — домен → канонический хост (схема/www/punycode/путь срезаются)
- `validate.py`     — обязательность period_start, границы периода, ISO-код гео
"""
