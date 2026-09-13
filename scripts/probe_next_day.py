#!/usr/bin/env python3
"""Шаг 5 чеклиста Ф7: два вопроса, ответ на которые даёт только второй день.

Оба вопроса про доверие к предохранителям, а не про формы ответов:

1. **Закрыт ли текущий месяц** (H2 в `docs/FINDINGS.md`). Правило кэша —
   «все месяцы до текущего календарного неизменяемы» (`collect/cache.closed_through`).
   Если Ahrefs достраивает прошлый месяц позже, мы навсегда сохраним неполные
   данные и не узнаем об этом: повторный сбор их не перезапросит.
2. **Растёт ли `units_usage_api_key`.** В течение сессии 12.09.2026 счётчик не
   сдвинулся ни разу, а заголовок `x-api-units-cost-total-actual` пришёл нулём.
   Если счётчик не растёт вообще, `preflight` всегда видит полный лимит —
   проверка написана, вызывается и ничего не охраняет. Ответ даёт **сдвиг между
   снимками**, а не само число: у ключа заказчика оно ненулевое в любом случае.

**Как пользоваться.** Первый запуск снимает снимок и сравнивать ему не с чем;
второй запуск через день-два сравнивает и называет вердикт. Снимки лежат в
`data/raw/` (вне git: там живые домены и их числа).

    AHREFS_PROVIDER=live python3 scripts/probe_next_day.py ahrefs.com
    AHREFS_PROVIDER=live python3 scripts/probe_next_day.py --quota-only

**Стоимость.** Запрос квоты бесплатен, и `--quota-only` — тоже: он спрашивает
только счётчик и ничего не записывает. История — один запрос на домен: три
строки по 11 units не добирают до минимума, поэтому 50 units за домен.

**Секреты.** Ключ читается конфигом и нигде не печатается.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.exc import SQLAlchemyError

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport
from ahrefs_cases.collect.budget import live_spend_since
from ahrefs_cases.collect.cache import closed_through
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.storage.session import dispose_engine, get_sessionmaker

_QUOTA_PATH = "/v3/subscription-info/limits-and-usage"
_ENVELOPE_KEY = "limits_and_usage"
_USED_KEY = "units_usage_api_key"
_SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
_SNAPSHOT_PREFIX = "снимок-месяцев-"

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


async def _live_spend(since: datetime) -> int | None:
    """Сколько units потратили живые прогоны с этого момента — по нашему журналу.

    Запрос не свой, а общий (`budget.live_spend_since`): этим же числом
    `preflight` вычитает из ответа Ahrefs расход, которого счётчик ещё не видел.
    Две копии разошлись бы ровно тогда, когда сверка начнёт что-то значить.

    Пробники в журнал не пишут: они ходят мимо прогона. Значит журнал — нижняя
    граница потраченного, и «счётчик сдвинулся меньше журнала» надо читать
    строго, а «больше» — с оговоркой.

    `None` — базы нет или она не отвечает. Это не повод не задавать вопрос
    квоте: ноль счётчика там, где точно тратили, виден и без журнала.
    """
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            return await live_spend_since(session, since)
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


def _report_counter(
    quota: dict[str, int], previous: dict[str, Any] | None, spent: int | None
) -> None:
    """Вердикт по счётчику расхода (H8): двигается ли он вообще.

    **Сравнивается сдвиг, а не абсолютное число.** Первая редакция считала
    ответом «счётчик больше потраченного» — и печатала бы «всё хорошо» на
    счётчике, который стоит с прошлого года: у ключа заказчика он и так
    полмиллиона. Живой запуск 13.09.2026 показал это сразу, и класс ошибки тот
    же, что у урока L53: величина, которая выглядит как ответ, но им не является.

    Цена ошибки — весь `collect/quota.py`: остаток считается как
    `limit - used`, и при неподвижном `used` preflight всегда видит полный
    лимит, то есть пропускает любую смету.
    """
    print("\n=== Счётчик расхода (0 units) ===")
    for key in sorted(quota):
        print(f"    {key} = {quota[key]}")
    used = quota.get(_USED_KEY)
    if used is None:
        print(f"  ✗ поля {_USED_KEY!r} в ответе нет — preflight скажет «остаток неизвестен»")
        return

    was = (previous or {}).get("quota", {}).get(_USED_KEY)
    if was is None:
        print(
            f"  · {_USED_KEY} = {used}; сдвиг покажет только второй снимок.\n"
            "    Абсолютное число ответом не является: у ключа заказчика оно ненулевое\n"
            "    независимо от того, считает Ahrefs наши запросы или нет"
        )
        return

    moved = used - was
    print(f"  сдвиг счётчика с прошлого снимка: {moved} units (было {was}, стало {used})")
    if spent is not None:
        print(f"  наш журнал за тот же промежуток: {spent} units (пробники в него не пишут)")

    if moved == 0 and spent:
        print(
            "  ✗ счётчик не сдвинулся при потраченном по журналу — значит остаток,\n"
            "    который видит preflight, не уменьшается. Предохранитель написан,\n"
            "    вызывается и ничего не охраняет: считать расход по своему журналу"
        )
    elif moved > 0:
        note = ""
        if spent:
            note = (
                f"\n    Наша смета {'завышает' if moved < spent else 'занижает'} факт: "
                f"{spent} против {moved} — {abs(moved - spent) / spent * 100:.0f} %"
            )
        print(f"  ✓ счётчик растёт — запросы тарифицируются, остаток из API годен{note}")
    else:
        print(
            "  · счётчик не изменился, но и по журналу ничего не тратили —\n"
            "    замер ничего не доказывает. Повторить после прогона"
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


def _taken_at(snapshot: dict[str, Any] | None) -> datetime:
    """Момент прошлого снимка. Нечитаемый — считаем сутки назад: промежуток,
    посчитанный шире настоящего, завысит журнал, а не занизит, и вывод
    «счётчик отстаёт» из него получить нельзя."""
    raw = (snapshot or {}).get("taken_at")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            print(f"дата снимка не разобралась ({raw!r}) — считаю журнал за сутки")
    return datetime.now(UTC) - timedelta(days=1)


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


async def _collect(
    domains: list[str], months: int, previous: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Снять показания: счётчик расхода и трафик по последним месяцам."""
    transport = AhrefsTransport()
    spent = await _live_spend(_taken_at(previous)) if previous else None
    try:
        quota = await _quota(transport)
        _report_counter(quota, previous, spent)
        traffic = {domain: await _months(transport, domain, months) for domain in domains}
    except ValueError as exc:
        print(f"\nответ не разобрался: {exc}", file=sys.stderr)
        return None
    return {
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "quota": quota,
        "traffic": traffic,
    }


def _refuse_reason() -> str | None:
    """Почему запускать нельзя, или `None`.

    Отдельной функцией, а не двумя `if` внутри `_main`: без этого шва оракул на
    «что пробник записывает» упирается в отказ фикстуры и проходит по неверной
    причине — зелёным, ничего не проверив.
    """
    if config.ahrefs.provider != "live":
        return "провайдер не live: фикстура отвечает своей же формулой"
    if not config.ahrefs.api_key:
        return "нет AHREFS_API_KEY"
    return None


def _main(domains: list[str], months: int, directory: Path, *, quota_only: bool) -> int:
    """Снимок, сравнение, сохранение. Файлы читаются и пишутся здесь,
    а не внутри `_collect`: блокирующий диск в асинхронной функции — запрет
    проекта (`ASYNC240`), и обходить его ради двух строк незачем."""
    refused = _refuse_reason()
    if refused is not None:
        print(refused, file=sys.stderr)
        return _EXIT_NOT_LIVE

    earlier = _previous_snapshot(directory)
    previous = earlier[1] if earlier else None
    current = asyncio.run(_collect([] if quota_only else domains, months, previous))
    if current is None:
        return _EXIT_BROKEN_ANSWER

    if quota_only:
        # Снимок НЕ пишется: он был бы без месяцев и затёр бы полный снимок того
        # же дня — завтрашнее сравнение по H2 осталось бы без вчерашних чисел.
        # Дешёвая проверка не имеет права портить дорогую.
        print("\nтолько квота: снимок не записан, месяцы не запрашивались")
        return 0
    if earlier is None:
        print("\nснимка для сравнения нет — это первый. Повторите запуск через день-два")
    else:
        print(f"\nсравниваем с {earlier[0].name}")
        _compare(earlier[1], current)

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
    parser.add_argument(
        "--quota-only",
        action="store_true",
        help="только счётчик расхода: 0 units, месяцы не запрашиваются",
    )
    args = parser.parse_args()
    raise SystemExit(
        _main(
            args.domains or ["ahrefs.com"],
            args.months,
            args.snapshot_dir,
            quota_only=args.quota_only,
        )
    )
