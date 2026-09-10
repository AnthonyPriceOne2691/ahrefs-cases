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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ahrefs_cases import config
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.intake.accept import (
    SourceNotFoundError,
    UnknownSourceError,
    accept,
    read_source,
)
from ahrefs_cases.intake.gsheet_source import SheetAccessError, SheetLinkError
from ahrefs_cases.storage.session import dispose_engine, get_sessionmaker

_SOURCE_ERRORS = (SourceNotFoundError, UnknownSourceError, SheetLinkError, SheetAccessError)
_EXIT_BAD_SOURCE = 2


async def _intake(reference: str) -> int:
    """Приём одного источника. Ошибка источника — сообщение, а не трассировка.

    Опечатка в пути и закрытая таблица — самые частые ошибки запуска, и
    отвечать на них стеком `io.open` значит требовать от человека читать
    трассировку ради строки «файла нет».
    """
    try:
        table = read_source(reference)
    except _SOURCE_ERRORS as exc:
        print(f"источник не прочитан: {exc}", file=sys.stderr)
        return _EXIT_BAD_SOURCE

    async with get_sessionmaker()() as session:
        report = await accept(session, table)
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.accepted else 1


async def _collect() -> int:
    async with get_sessionmaker()() as session:
        report = await collect_all(session)
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _main(args: argparse.Namespace) -> int:
    print(f"провайдер: {config.ahrefs.provider}", flush=True)
    try:
        if args.command == "intake":
            return await _intake(args.source)
        if args.command == "collect":
            return await _collect()
        code = await _intake(args.source)
        return code or await _collect()
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    intake_parser = sub.add_parser("intake", help="принять список проектов")
    intake_parser.add_argument("source", help="путь к .csv/.xlsx или ссылка на Google Sheet")

    sub.add_parser("collect", help="собрать историю по проектам в базе")

    all_parser = sub.add_parser("all", help="принять список и сразу собрать")
    all_parser.add_argument("source", help="путь к .csv/.xlsx или ссылка на Google Sheet")

    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
