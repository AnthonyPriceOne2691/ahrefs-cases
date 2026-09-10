#!/usr/bin/env python3
"""Разведка живого Ahrefs: проверить форму ответов, потратив минимум units.

Инструмент шага 1–4 из `docs/PHASE7_CHECKLIST.md`. Отвечает на вопросы, на
которые нельзя ответить без ключа: как называются поля остатка квоты, по
какому ключу лежит список истории, как выглядят даты, сколько стоит запрос.

**Стоимость.** Запрос квоты бесплатен. Каждый history-запрос по нашей модели
стоит 50 units; скрипт делает их столько, сколько доменов передано (по
умолчанию один). Ничего не пишет в базу и не запускает прогон.

**Секреты.** Ключ читается конфигом из `.env` (`AHREFS_API_KEY`) и нигде не
печатается — ни в выводе, ни в логах. Наружу идут только имена полей, формы
дат и числа.

    AHREFS_PROVIDER=live python3 scripts/probe_ahrefs.py ahrefs.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport
from ahrefs_cases.collect.endpoints import ALL_SPECS, METRICS_HISTORY

_QUOTA_PATH = "/v3/subscription-info/limits-and-usage"
_UNITS_HEADERS = (
    "x-api-units-cost-total-actual",
    "x-api-units-cost-total",
    "x-api-units-cost-row",
)


def _shape(value: Any, depth: int = 0) -> str:
    """Форма значения без самих данных, кроме коротких примеров."""
    if isinstance(value, dict):
        keys = ", ".join(sorted(value)[:12])
        return f"объект {{{keys}}}"
    if isinstance(value, list):
        if not value:
            return "пустой список"
        return f"список[{len(value)}] из {_shape(value[0], depth + 1)}"
    return f"{type(value).__name__}"


def _walk(value: Any, prefix: str = "") -> list[str]:
    """Все числовые поля с их путями — чтобы найти остаток на любой глубине."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            found.extend(_walk(inner, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, int | float) and not isinstance(value, bool):
        found.append(f"{prefix} = {value}")
    return found


async def _probe_quota(transport: AhrefsTransport) -> None:
    print("\n=== Шаг 1. Квота (0 units) ===")
    response = await transport.get(_QUOTA_PATH, {})
    print(f"форма ответа: {_shape(response.payload)}")
    for expected in ("units_limit", "units_usage"):
        mark = "✓" if expected in response.payload else "✗"
        print(f"  {mark} ожидали ключ {expected!r} на верхнем уровне")
    print("числовые поля по путям (ищем остаток):")
    for line in _walk(response.payload)[:20]:
        print(f"    {line}")


async def _probe_history(
    transport: AhrefsTransport,
    domain: str,
    date_from: str,
    fields: tuple[str, ...] | None = None,
) -> None:
    spec = METRICS_HISTORY
    select = fields or spec.select
    print(f"\n=== История по {domain} с {date_from}, полей {len(select) - 1} ===")
    params = {
        "target": domain,
        "mode": "subdomains",
        "date_from": date_from,
        "history_grouping": config.ahrefs.history_grouping,
        "select": ",".join(select),
        "output": "json",
    }
    response = await transport.get(spec.path, params)

    print(f"форма ответа: {_shape(response.payload)}")
    mark = "✓" if spec.list_key in response.payload else "✗"
    print(f"  {mark} ожидали ключ списка {spec.list_key!r}")

    rows = next((v for v in response.payload.values() if isinstance(v, list)), [])
    if rows:
        first, last = rows[0], rows[-1]
        print(f"строк: {len(rows)}; поля строки: {', '.join(sorted(first))}")
        print(f"первая: {first}")
        print(f"последняя: {last}")
        dates = [row.get("date") for row in rows if isinstance(row, dict)]
        monthly = all(isinstance(d, str) and d[8:10] in {"01", "1"} for d in dates if d)
        print(f"  {'✓' if monthly else '✗'} все точки — первые числа месяцев (H4)")
        print(f"  глубина: с {dates[0]} по {dates[-1]} — просили с 2024-01-01 (H3)")
    rows_count = len(rows)
    print(f"стоимость: estimated={response.units_estimated}, actual={response.units_actual}")
    print(f"наша модель обещала: {spec.estimate_units()} (H1)")
    if rows_count and response.units_estimated:
        per_row = response.units_estimated / rows_count
        print(f"  → на строку: {per_row:.2f} units при {len(select) - 1} полях")
    print("все заголовки цены, какие пришли:")
    for name, value in sorted(response.headers.items()):
        if name.lower().startswith("x-api"):
            print(f"    {name}: {value}")


async def _main(domains: list[str]) -> int:
    if config.ahrefs.provider != "live":
        print("провайдер не live: разведка не нужна, fixture ничего нового не покажет", file=sys.stderr)
        return 2
    if not config.ahrefs.api_key:
        print("нет AHREFS_API_KEY", file=sys.stderr)
        return 2

    transport = AhrefsTransport()
    print(f"endpoint'ов в спеке: {len(ALL_SPECS)}; проверяем квоту и metrics-history")
    try:
        await _probe_quota(transport)
        # Два замера разной глубины: одна точка не отличает «цена за запрос»
        # от «цена за строку», а вся смета стоит на этом различии.
        # Три замера: они отличают «цена за строку» от «фиксированная цена
        # плюс строки» и показывают, есть ли минимум за запрос. Одной точки
        # для формулы не хватает, а от формулы зависит вся смета.
        for domain in domains:
            await _probe_history(transport, domain, "2026-09-01")  # 1 строка
            await _probe_history(transport, domain, "2026-07-01")  # 3 строки
            await _probe_history(transport, domain, "2026-01-01", fields=("date", "org_traffic"))
    except Exception as exc:
        print(f"\nответ не разобрался: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domains", nargs="*", default=["ahrefs.com"], help="домены для проверки")
    raise SystemExit(asyncio.run(_main(parser.parse_args().domains or ["ahrefs.com"])))
