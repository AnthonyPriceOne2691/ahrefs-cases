#!/usr/bin/env python3
"""Шаг 5 чеклиста Ф7: два вопроса, ответ на которые даёт только второй день.

Оба вопроса про доверие к предохранителям, а не про формы ответов:

1. **Закрыт ли текущий месяц** (H2 в `docs/FINDINGS.md`). Правило кэша —
   «все месяцы до текущего календарного неизменяемы» (`collect/cache.closed_through`).
   Если Ahrefs достраивает прошлый месяц позже, мы навсегда сохраним неполные
   данные и не узнаем об этом: повторный сбор их не перезапросит.
2. **Растёт ли `units_usage_api_key`.** 12.09.2026 счётчик не сдвинулся при
   ~2 262 потраченных units, а заголовок `x-api-units-cost-total-actual` пришёл
   нулём. Если счётчик не растёт вообще, `preflight` всегда видит полный лимит
   — проверка написана, вызывается и ничего не охраняет.

**Как пользоваться.** Первый запуск снимает снимок и сравнивать ему не с чем;
второй запуск через день-два сравнивает и называет вердикт. Снимки лежат в
`data/raw/` (вне git: там живые домены и их числа).

    AHREFS_PROVIDER=live python3 scripts/probe_next_day.py ahrefs.com

**Стоимость.** Запрос квоты бесплатен. История — один запрос на домен: три
строки по 11 units не добирают до минимума, поэтому 50 units за домен.

**Секреты.** Ключ читается конфигом и нигде не печатается.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport
from ahrefs_cases.collect.cache import closed_through
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.storage._enums import LedgerKind
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.units_ledger import UnitsLedger
from ahrefs_cases.storage.session import dispose_engine, get_sessionmaker

_QUOTA_PATH = "/v3/subscription-info/limits-and-usage"
_ENVELOPE_KEY = "limits_and_usage"
_USED_KEY = "units_usage_api_key"
_SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
_SNAPSHOT_PREFIX = "снимок-месяцев-"

_FIRST_LIVE_RUN = date(2026, 9, 12)
"""День первого живого прогона: счётчик сравнивается с расходом от него, а не
за всё время — до этого дня живых запросов не было вовсе."""

_EXIT_NOT_LIVE = 2
_EXIT_BROKEN_ANSWER = 1


def _today() -> date:
    """Сегодня по UTC — тем же часовым поясом, которым размечены ответы Ahrefs."""
    return datetime.now(UTC).date()


def _month_start(anchor: date) -> date:
    return date(anchor.year, anchor.month, 1)


def _shift_months(anchor: date, months: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


async def _live_spend(started_after: date) -> int | None:
    """Сколько units потратили живые прогоны с этой даты — по нашему журналу.

    Счётчик Ahrefs сравнивается **с журналом**, а не с числом из памяти: журнал
    и есть то, чем мы объясняем счёт, и если он разойдётся со счётчиком
    провайдера, разойдётся именно в этом месте.

    `None` — базы нет или она не отвечает. Это не повод не задавать вопрос
    квоте: часть ответа (ноль там, где точно тратили) видна и без журнала.
    """
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            spent = await session.scalar(
                select(func.coalesce(func.sum(UnitsLedger.units_actual), 0))
                .join(Run, Run.id == UnitsLedger.run_id)
                .where(
                    UnitsLedger.kind == LedgerKind.SPENT,
                    Run.params_snapshot["provider"].astext == "live",
                    UnitsLedger.created_at
                    >= datetime(
                        started_after.year, started_after.month, started_after.day, tzinfo=UTC
                    ),
                )
            )
        return int(spent or 0)
    except (SQLAlchemyError, OSError) as exc:
        print(f"журнал прогонов недоступен ({type(exc).__name__}: {exc}) — сравнить не с чем")
        return None
    finally:
        await dispose_engine()


async def _quota(transport: AhrefsTransport) -> dict[str, int]:
    """Числа квоты как есть. Разбор строгий: чужая форма — не «остаток ноль»."""
    response = await transport.get(_QUOTA_PATH, {})
    envelope = response.payload.get(_ENVELOPE_KEY)
    if not isinstance(envelope, dict):
        message = (
            f"subscription-info: ожидали объект по ключу {_ENVELOPE_KEY!r}, "
            f"пришли ключи: {', '.join(sorted(response.payload)) or '(пусто)'}"
        )
        raise ValueError(message)
    return {key: int(value) for key, value in envelope.items() if isinstance(value, int)}


def _report_counter(quota: dict[str, int], spent: int | None) -> None:
    """Вердикт по счётчику: сдвинулся ли он на то, что мы потратили."""
    print("\n=== Счётчик расхода (0 units) ===")
    for key in sorted(quota):
        print(f"    {key} = {quota[key]}")
    used = quota.get(_USED_KEY)
    if used is None:
        print(f"  ✗ поля {_USED_KEY!r} в ответе нет — preflight скажет «остаток неизвестен»")
        return
    if spent is None:
        print(f"  · {_USED_KEY} = {used}; журнала под рукой нет, сравнить не с чем")
        return
    print(f"  журнал живых прогонов с 12.09: {spent} units")
    if used == 0 and spent > 0:
        print(
            "  ✗ счётчик стоит на нуле после потраченного — значит остаток, который\n"
            "    видит preflight, не уменьшается никогда. Предохранитель написан,\n"
            "    вызывается и ничего не охраняет: занести в docs/FINDINGS.md и\n"
            "    считать расход по собственному журналу, а не по ответу Ahrefs"
        )
    elif used >= spent > 0:
        print(
            f"  ✓ счётчик обновился с задержкой: {used} ≥ потраченных {spent}.\n"
            "    Значит вчерашний ноль — «обновляется раз в сутки», а не\n"
            "    «эти запросы не тарифицируются». Остаток из API годен для preflight"
        )
    else:
        print(
            f"  · счётчик {used} меньше потраченного {spent} — сам по себе не ответ.\n"
            "    Так выглядит и частичный учёт, и чужой прогон на том же ключе.\n"
            "    Повторить замер после следующего прогона"
        )


async def _months(transport: AhrefsTransport, domain: str, months: int) -> dict[str, float]:
    """Трафик по месяцам: один запрос узким окном (50 units)."""
    date_from = _shift_months(_month_start(_today()), -(months - 1))
    params = {
        "target": domain,
        "mode": "subdomains",
        "date_from": date_from.isoformat(),
        "history_grouping": config.ahrefs.history_grouping,
        "select": ",".join(METRICS_HISTORY.select),
        "output": "json",
    }
    response = await transport.get(METRICS_HISTORY.path, params)
    rows = response.payload.get(METRICS_HISTORY.list_key)
    if not isinstance(rows, list):
        message = (
            f"{METRICS_HISTORY.name}: ожидали список по ключу {METRICS_HISTORY.list_key!r}, "
            f"пришли ключи: {', '.join(sorted(response.payload)) or '(пусто)'}"
        )
        raise ValueError(message)
    values = {
        str(row["date"])[:10]: float(row["org_traffic"])
        for row in rows
        if isinstance(row, dict) and "date" in row and "org_traffic" in row
    }
    print(
        f"\n=== {domain}: {len(values)} мес. с {date_from.isoformat()} "
        f"(estimated={response.units_estimated}) ==="
    )
    for month in sorted(values):
        print(f"    {month}  {values[month]:,.0f}".replace(",", " "))
    return values


def _previous_snapshot(directory: Path) -> tuple[Path, dict[str, Any]] | None:
    """Самый свежий снимок прошлых запусков. Его и сравниваем."""
    files = sorted(directory.glob(f"{_SNAPSHOT_PREFIX}*.json"))
    if not files:
        return None
    latest = files[-1]
    return latest, json.loads(latest.read_text(encoding="utf-8"))


def _compare(previous: dict[str, Any], current: dict[str, Any]) -> None:
    """Вердикт по H2: какие месяцы поменялись за время между снимками.

    Различаем три исхода, потому что лечатся они по-разному: поменялся только
    текущий — правило кэша верно; поменялся закрытый — граница `closed_through`
    обязана отступить на месяц дальше, иначе неполные данные останутся навсегда;
    не поменялось ничего — вопрос открыт, а не закрыт (день мог пройти без
    обновления у самого Ahrefs).
    """
    print(f"\n=== Что изменилось с {previous.get('taken_at', '?')} ===")
    border = closed_through(_today())
    changed_open: list[str] = []
    changed_closed: list[str] = []
    for domain, months in current.get("traffic", {}).items():
        was = previous.get("traffic", {}).get(domain, {})
        for month in sorted(months):
            before = was.get(month)
            if before is None or before == months[month]:
                continue
            mark = "закрытый" if date.fromisoformat(month) <= border else "текущий"
            print(f"    {domain} {month} ({mark}): {before:,.0f} → {months[month]:,.0f}")
            (changed_closed if mark == "закрытый" else changed_open).append(f"{domain} {month}")

    if changed_closed:
        print(
            "  ✗ H2 ОПРОВЕРГНУТА: Ahrefs дописывает месяц, который мы считаем закрытым.\n"
            "    `cache.closed_through` обязан отступить на месяц дальше, иначе повторный\n"
            "    сбор никогда не перезапросит эти точки — и кейс уйдёт клиенту по неполным"
        )
    elif changed_open:
        print(
            "  ✓ H2 ПОДТВЕРЖДЕНА: меняется только текущий месяц, закрытые стоят.\n"
            "    Правило кэша («неизменяемы все месяцы до текущего») верно"
        )
    else:
        print(
            "  · не изменилось ничего — вопрос остаётся открытым, а не закрытым.\n"
            "    Повторить через несколько дней: сутки Ahrefs мог просто не считать"
        )


async def _collect(domains: list[str], months: int) -> dict[str, Any] | None:
    """Снять показания: счётчик расхода и трафик по последним месяцам."""
    transport = AhrefsTransport()
    spent = await _live_spend(_FIRST_LIVE_RUN)
    try:
        quota = await _quota(transport)
        _report_counter(quota, spent)
        traffic = {domain: await _months(transport, domain, months) for domain in domains}
    except ValueError as exc:
        print(f"\nответ не разобрался: {exc}", file=sys.stderr)
        return None
    return {
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "quota": quota,
        "traffic": traffic,
    }


def _main(domains: list[str], months: int, directory: Path) -> int:
    """Снимок, сравнение, сохранение. Файлы читаются и пишутся здесь,
    а не внутри `_collect`: блокирующий диск в асинхронной функции — запрет
    проекта (`ASYNC240`), и обходить его ради двух строк незачем."""
    if config.ahrefs.provider != "live":
        print("провайдер не live: фикстура отвечает своей же формулой", file=sys.stderr)
        return _EXIT_NOT_LIVE
    if not config.ahrefs.api_key:
        print("нет AHREFS_API_KEY", file=sys.stderr)
        return _EXIT_NOT_LIVE

    earlier = _previous_snapshot(directory)
    current = asyncio.run(_collect(domains, months))
    if current is None:
        return _EXIT_BROKEN_ANSWER

    if earlier is None:
        print("\nснимка для сравнения нет — это первый. Повторите запуск через день-два")
    else:
        path, previous = earlier
        print(f"\nсравниваем с {path.name}")
        _compare(previous, current)

    directory.mkdir(parents=True, exist_ok=True)
    saved = directory / f"{_SNAPSHOT_PREFIX}{_today().isoformat()}.json"
    saved.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"снимок сохранён: {saved}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domains", nargs="*", default=["ahrefs.com"], help="домены для снимка")
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="сколько последних месяцев брать: три строки стоят те же 50 units, что одна",
    )
    parser.add_argument("--snapshot-dir", type=Path, default=_SNAPSHOT_DIR)
    args = parser.parse_args()
    raise SystemExit(_main(args.domains or ["ahrefs.com"], args.months, args.snapshot_dir))
