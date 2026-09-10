"""Сбор исторических серий из Ahrefs API v3 — единственный платный слой.

Ф1. Темы модулей:
- `plan.py`             — план сбора: что и кому дёргаем (двухступенчатая воронка)
- `ahrefs_transport.py` — один HTTP-запрос к /v3/site-explorer/<endpoint> + разбор units-headers
- `endpoints.py`        — спеки history-endpoint'ов (данные, не код), минимальный select
- `series.py`           — ответ endpoint'а → MetricPoint-строки, инкрементальный date_from
- `cache.py`            — «закрытые месяцы навсегда» + single-flight по домену
- `budget.py`           — смета прогона, мягкий стоп, локальный счётчик потраченных units
- `quota.py`            — preflight по остатку units (бесплатный endpoint)
- `run_journal.py`      — журнал прогонов: сколько потратили, что упало

Экономия units — приоритет №1 этого слоя, см. ../../../docs/UNITS_ECONOMY.md.
Слой отделён от classify/cases сознательно: пороги калибруются итеративно, и
каждая итерация не должна стоить units.
"""
