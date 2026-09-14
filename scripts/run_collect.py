#!/usr/bin/env python3
"""Приём списка и прогон сбора из командной строки.

HTTP-запуск придёт в Ф5, очередь — там же. До тех пор это единственный способ
запустить сквозной путь целиком, и он же — сквозной smoke поставки:

    python3 scripts/run_collect.py intake config/projects.example.csv
    python3 scripts/run_collect.py collect
    python3 scripts/run_collect.py all config/projects.example.csv

Провайдер берётся из конфига и по умолчанию `fixture`: сеть и units не тратятся.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


from ahrefs_cases import config
from ahrefs_cases.cli.case_commands import pack_cases, render_case, show_cases
from ahrefs_cases.cli.collect_commands import (
    OnlyNotADomainError,
    _canonical,
    _case_data,
    _chosen_source,
    _classify,
    _collect,
    _diagnose,
    _explain,
    _intake,
    _named,
    _only,
    _preview,
    _recalc,
    _stage2,
)
from ahrefs_cases.cli.user_commands import add_user
from ahrefs_cases.intake.accept import (
    SourceNotFoundError,
    UnknownSourceError,
)
from ahrefs_cases.intake.gsheet_source import SheetAccessError, SheetLinkError
from ahrefs_cases.storage.session import dispose_engine

_SOURCE_ERRORS = (SourceNotFoundError, UnknownSourceError, SheetLinkError, SheetAccessError)
_EXIT_BAD_SOURCE = 2
_EXIT_RUN_FAILED = 3
_EXIT_CONTENT_BLOCKED = 4
_EXIT_INTERRUPTED = 130


async def _main(args: argparse.Namespace) -> int:
    """Разбор команды. Наружу не выходит ни одна необработанная ошибка.

    Коды различают причины, потому что по ним принимают разные решения:
    2 — список не прочитан (чинит человек, правя путь или доступ),
    3 — прогон упал (смотреть журнал прогона и логи),
    4 — кейс заблокирован контент-запретом (править входной файл, не логи),
    130 — прервано с клавиатуры (не ошибка вовсе).
    """
    print(f"провайдер: {config.ahrefs.provider}", flush=True)
    try:
        if args.command == "intake":
            return await _intake(args.source)
        if args.command == "collect":
            return await _collect(refresh=args.refresh, only=_only(args.only))
        if args.command == "stage2":
            return await _stage2(refresh=args.refresh, only=_only(args.only))
        if args.command == "classify":
            return await _classify()
        if args.command == "case-data":
            return await _case_data(refresh=args.refresh, only=_only(args.only))
        if args.command == "recalc":
            return await _recalc(args.version, make_active=args.activate)
        if args.command == "preview":
            return await _preview(args.version)
        if args.command == "cases":
            return await show_cases(_named(args.domain), args.version, _chosen_source(args))
        if args.command == "render":
            return await render_case(_canonical(args.domain), _chosen_source(args))
        if args.command == "pack":
            return await pack_cases(_chosen_source(args))
        if args.command == "useradd":
            return await add_user(args.email, args.group)
        if args.command == "diagnose":
            return await _diagnose(_named(args.domain))
        if args.command == "explain":
            return await _explain(_canonical(args.domain))
        code = await _intake(args.source)
        return code or await _collect(refresh=args.refresh)
    except OnlyNotADomainError as exc:
        # Отдельный код возврата: «в --only не домен» чинится правкой команды,
        # а не повтором прогона. Общий обработчик ниже назвал бы это «прогон
        # не завершён» — то есть отправил бы человека смотреть журнал прогона,
        # которого не было.
        print(f"--only: {exc}", file=sys.stderr)
        return _EXIT_BAD_SOURCE
    except KeyboardInterrupt:
        # Не ошибка: человек остановил прогон сам. Уже собранное сохранено
        # чекпойнтами, следующий запуск догрузит остаток.
        print("прервано; собранное сохранено, повторный запуск догрузит остаток", file=sys.stderr)
        return _EXIT_INTERRUPTED
    except Exception as exc:
        # Последний рубеж: сервис не имеет права падать трассировкой в лицо.
        # Полный стек уходит в лог, человеку — строка и код возврата.
        logging.getLogger(__name__).exception("cli_command_failed", extra={"command": args.command})
        print(f"прогон не завершён: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "подробности — в логе; журнал прогона показывает, что успело собраться", file=sys.stderr
        )
        return _EXIT_RUN_FAILED
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    intake_parser = sub.add_parser("intake", help="принять список проектов")
    intake_parser.add_argument("source", help="путь к .csv/.xlsx или ссылка на Google Sheet")

    collect_parser = sub.add_parser("collect", help="собрать историю по проектам в базе")
    collect_parser.add_argument(
        "--only",
        default=None,
        help="домены через запятую или файл со списком: собрать только их, а не всю базу",
    )
    stage2_parser = sub.add_parser(
        "stage2", help="шаг 2 воронки: дорогие метрики только по кандидатам"
    )
    sub.add_parser("classify", help="классифицировать проекты по действующим порогам")
    case_parser = sub.add_parser(
        "case-data", help="докупить данные под кейсы: кривая позиций и стоимость трафика"
    )
    recalc_parser = sub.add_parser(
        "recalc", help="пересчитать вердикты по версии порогов (без обращения к Ahrefs)"
    )
    recalc_parser.add_argument("version", help="версия порогов, например 2026-09-A")
    recalc_parser.add_argument(
        "--activate",
        action="store_true",
        help="сделать версию действующей: следующая классификация пойдёт по ней",
    )
    preview_parser = sub.add_parser(
        "preview", help="показать, кто сменит группу при этой версии порогов (без записи)"
    )
    preview_parser.add_argument("version", help="версия порогов, например 2026-09-A")
    cases_parser = sub.add_parser(
        "cases", help="показать, что соберётся в кейсы (без записи и без Ahrefs)"
    )
    cases_parser.add_argument(
        "domain", nargs="?", default=None, help="домен; без него — все проекты"
    )
    cases_parser.add_argument(
        "--version",
        default=None,
        help="версия порогов; без неё — действующая. Кейс собирается по вердикту этой версии",
    )
    pack_parser = sub.add_parser("pack", help="собрать кейсы «хороших» и «средних» в ZIP-архив")
    user_parser = sub.add_parser("useradd", help="завести пользователя сервиса (пароль спросит)")
    user_parser.add_argument("email", help="почта — она же логин")
    user_parser.add_argument("group", choices=["engineer", "admin", "user"], help="группа доступа")
    render_parser = sub.add_parser("render", help="собрать кейс проекта и положить PDF на диск")
    render_parser.add_argument("domain", help="канонический домен проекта")
    diagnose_parser = sub.add_parser(
        "diagnose", help="разбор «плохих»: что просело, когда началось, потеряны ли домены"
    )
    diagnose_parser.add_argument(
        "domain", nargs="?", default=None, help="домен; без него — список всех «плохих»"
    )
    explain_parser = sub.add_parser("explain", help="показать вердикт одного домена по условиям")
    explain_parser.add_argument("domain", help="канонический домен проекта")
    all_parser = sub.add_parser("all", help="принять список и сразу собрать")
    all_parser.add_argument("source", help="путь к .csv/.xlsx или ссылка на Google Sheet")

    # Источник рядов — у каждой читающей команды. Чтение уже купленного не
    # обязано требовать живого провайдера: это разные вопросы, и смешивать их
    # значит снимать запрет ради операции, которая ключом не пользуется.
    for reading_parser in (cases_parser, render_parser, pack_parser):
        reading_parser.add_argument(
            "--source",
            choices=("live", "fixture"),
            default=None,
            help="какие ряды читать; без флага — как у провайдера",
        )

    # Область действия — у каждой платящей команды. Забыть её у одной означает
    # заплатить за всё, что найдётся в базе: ровно так 12.09.2026 живой прогон
    # ушёл в Ahrefs за отладочными доменами стенда.
    for paying_parser in (stage2_parser, case_parser):
        paying_parser.add_argument(
            "--only",
            default=None,
            help="домены через запятую или файл со списком: платить только за них",
        )

    for parser_with_refresh in (collect_parser, stage2_parser, case_parser, all_parser):
        parser_with_refresh.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "игнорировать кэш и перезапросить историю целиком. "
                "Стоит полной цены прогона — нужен, если Ahrefs пересчитал данные задним числом"
            ),
        )

    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
