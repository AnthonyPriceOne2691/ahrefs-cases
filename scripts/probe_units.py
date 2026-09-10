#!/usr/bin/env python3
"""Матрица замеров: где именно прячется экономия units.

Разведка уже показала главное — биллинг построчный (`10 × поле + 1` за строку,
минимум 50 за запрос). Отсюда шесть гипотез об экономии, и все они проверяются
только замером, потому что документация о таком молчит.

Каждый замер печатает строку таблицы: что просили, сколько строк пришло, во
что обошлось. Ничего не пишет в базу и не запускает прогон.

    AHREFS_PROVIDER=live python3 scripts/probe_units.py ahrefs.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport

_HISTORY = "/v3/site-explorer/metrics-history"
_METRICS = "/v3/site-explorer/metrics"


@dataclass(frozen=True, slots=True)
class Probe:
    """Один замер: зачем он и что спрашиваем."""

    label: str
    hypothesis: str
    path: str
    params: dict[str, str]


def _probes(domain: str) -> list[Probe]:
    common = {"target": domain, "mode": "subdomains", "output": "json"}
    monthly = {"history_grouping": "monthly"}
    return [
        Probe(
            "история 18 мес, 1 поле",
            "база для сравнения: столько стоит нынешняя схема",
            _HISTORY,
            {**common, **monthly, "date_from": "2025-03-01", "select": "date,org_traffic"},
        ),
        Probe(
            "история 18 мес, 2 поля",
            "цена второго поля: стоит ли org_cost того",
            _HISTORY,
            {**common, **monthly, "date_from": "2025-03-01", "select": "date,org_traffic,org_cost"},
        ),
        Probe(
            "окно А: 2 месяца",
            "date_to режет строки? тогда точки А и Б дешевле всей истории",
            _HISTORY,
            {
                **common,
                **monthly,
                "date_from": "2025-03-01",
                "date_to": "2025-04-01",
                "select": "date,org_traffic",
            },
        ),
        Probe(
            "окно Б: 2 месяца",
            "вторая половина той же идеи",
            _HISTORY,
            {
                **common,
                **monthly,
                "date_from": "2026-08-01",
                "date_to": "2026-09-01",
                "select": "date,org_traffic",
            },
        ),
        Probe(
            "повтор окна А",
            "кэш Ahrefs: `x-api-cache: hit` даёт скидку или нет",
            _HISTORY,
            {
                **common,
                **monthly,
                "date_from": "2025-03-01",
                "date_to": "2025-04-01",
                "select": "date,org_traffic",
            },
        ),
        Probe(
            "группировка yearly",
            "меньше строк — меньше цена? для точек А и Б месяцы не обязательны",
            _HISTORY,
            {
                **common,
                "history_grouping": "yearly",
                "date_from": "2025-03-01",
                "select": "date,org_traffic",
            },
        ),
        Probe(
            "точечные метрики (metrics)",
            "срез на дату вместо истории: дешевле ли двух точек",
            _METRICS,
            {**common, "date": "2026-09-01"},
        ),
    ]


async def _run(transport: AhrefsTransport, probe: Probe) -> tuple[int, int, int]:
    response = await transport.get(probe.path, probe.params)
    rows = int(response.headers.get("x-api-rows", 0) or 0)
    row_cost = int(response.headers.get("x-api-units-cost-row", 0) or 0)
    total = response.units_estimated
    cache = response.headers.get("x-api-cache", "?")
    print(f"{probe.label:26} строк {rows:3}  строка {row_cost:3}  итого {total:5}  кэш {cache}")
    print(f"{'':26} ← {probe.hypothesis}")
    return rows, row_cost, total


async def _main(domain: str) -> int:
    if config.ahrefs.provider != "live":
        print("нужен live-провайдер: на фикстурах цены выдуманы", file=sys.stderr)
        return 2

    transport = AhrefsTransport()
    print(f"домен: {domain}\n")
    results: dict[str, tuple[int, int, int]] = {}
    for probe in _probes(domain):
        try:
            results[probe.label] = await _run(transport, probe)
        except Exception as exc:
            print(f"{probe.label:26} ОТКАЗ: {type(exc).__name__}: {exc}")

    print("\n=== выводы ===")
    base = results.get("история 18 мес, 1 поле")
    window_a = results.get("окно А: 2 месяца")
    window_b = results.get("окно Б: 2 месяца")
    if base and window_a and window_b:
        points = window_a[2] + window_b[2]
        print(f"история целиком: {base[2]} units; две точки: {points} units")
        verdict = "точки дешевле" if points < base[2] else "история дешевле"
        print(f"  → {verdict} (разница {abs(base[2] - points)} units на домен)")
        print(f"  → на 100 доменов: {base[2] * 100} против {points * 100}")
    repeat = results.get("повтор окна А")
    if window_a and repeat:
        print(
            f"повтор того же запроса: {repeat[2]} против {window_a[2]} — "
            f"{'кэш экономит' if repeat[2] < window_a[2] else 'кэш не экономит'}"
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", nargs="?", default="ahrefs.com")
    raise SystemExit(asyncio.run(_main(parser.parse_args().domain)))
