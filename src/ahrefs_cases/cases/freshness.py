"""Объясняет ли собранный файл сегодняшнюю группу — или уже нет.

Кейс печатает числа того расчёта, которым собран, и хранит их в `highlights`.
Экран показывает действующий вердикт. Между ними помещается пересчёт, и после
него файл начинает говорить о проекте не то же самое, что карточка: у
`allthedifferences.com` 16.09.2026 на экране стояло «плохой, −99,9 %», а кнопка
отдавала прежний лист «+69 %» (Z30).

**Сверять по `verdict_id` бесполезно, и это главное в модуле.** Вердикт пишется
upsert'ом по паре «проект + версия порогов»: пересчёт той же версией
**перезаписывает строку**, оставляя тот же `id`. Формальная связь цела, числа
внутри другие. Поэтому сверяются сами числа — те, что напечатаны в файле,
против тех, что стоят в вердикте сейчас.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ahrefs_cases.cases.builder import CASE_GROUPS
from ahrefs_cases.storage.models.case import Case
from ahrefs_cases.storage.models.verdict import Verdict

_TOLERANCE = 0.001
"""Допуск сравнения: тысячная доля величины. Числа проходят через JSON и
округление подписей, и требовать побитового равенства значило бы объявлять
устаревшим каждый второй файл (урок L149: оракул, сравнивающий оценку на
точное равенство, судит по шуму)."""


def case_mismatch(case: Case, now: Verdict | None) -> str | None:
    """Почему файл больше не объясняет сегодняшнюю группу. `None` — объясняет.

    `gone` — вердикта проекта больше нет, `group` — кейс этой группе не
    положен, `verdict` — файл собран другим расчётом, `numbers` — расчёт тот
    же, а числа в файле другие (вердикт пересчитан поверх).
    """
    if now is None:
        return "gone"
    if now.group not in CASE_GROUPS:
        return "group"
    if case.verdict_id != now.id:
        return "verdict"
    printed = _printed(case.highlights)
    if not printed:
        return None
    before, after = _points(now)
    for subject, (was, became) in printed.items():
        if _differs(was, before.get(subject)) or _differs(became, after.get(subject)):
            return "numbers"
    return None


def _printed(highlights: Mapping[str, Any]) -> dict[str, tuple[float, float]]:
    picked = highlights.get("picked", [])
    rows = picked if isinstance(picked, list) else []
    return {
        str(row["subject"]): (float(row["before"]), float(row["after"]))
        for row in rows
        if isinstance(row, dict) and {"subject", "before", "after"} <= row.keys()
    }


def _points(verdict: Verdict) -> tuple[dict[str, float], dict[str, float]]:
    """Числа вердикта по метрикам: измеренные и посчитанные лежат врозь."""

    def flat(point: Mapping[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key in ("values", "derived"):
            part = point.get(key, {})
            if isinstance(part, dict):
                out.update({str(name): float(value) for name, value in part.items()})
        return out

    return flat(verdict.point_a), flat(verdict.point_b)


def _differs(printed: float, current: float | None) -> bool:
    if current is None:
        return True
    return abs(printed - current) > max(1.0, abs(current) * _TOLERANCE)
