"""Чтение входного списка проектов из CSV/XLSX.

Не реализовано (Ф1). Ожидаемые колонки — см. ../../../config/projects.example.csv:
domain (обязательна), period_start, period_end, niche, geo, target_mode, notes.

Кодировки: список почти наверняка придёт выгрузкой из Excel в cp1251, поэтому
парсер defensive — chardet + fallback-цепочка кодировок.
"""
