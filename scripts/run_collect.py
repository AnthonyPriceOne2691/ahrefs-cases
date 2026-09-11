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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.classify.diagnose import diagnose_domain, diagnose_poor
from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import activate, recalc
from ahrefs_cases.classify.rulesets import active_ruleset, seed_thresholds, thresholds_of
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.classify.verdicts import classify_all, classify_project
from ahrefs_cases.cli.case_commands import pack_cases, render_case, show_cases
from ahrefs_cases.collect.funnel import preliminary_candidates
from ahrefs_cases.collect.runner import collect_all, collect_case_data, collect_stage2
from ahrefs_cases.collect.scheme import PointWindows
from ahrefs_cases.intake.accept import (
    SourceNotFoundError,
    UnknownSourceError,
    accept,
    read_source,
)
from ahrefs_cases.intake.gsheet_source import SheetAccessError, SheetLinkError
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict
from ahrefs_cases.storage.session import dispose_engine, get_sessionmaker

_SOURCE_ERRORS = (SourceNotFoundError, UnknownSourceError, SheetLinkError, SheetAccessError)
_EXIT_BAD_SOURCE = 2
_EXIT_RUN_FAILED = 3
_EXIT_CONTENT_BLOCKED = 4
_EXIT_INTERRUPTED = 130


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


async def _point_windows(session: AsyncSession) -> PointWindows:
    """Окна точек из активной версии порогов — сюда, а не внутрь `collect`.

    Слои: контракт `layers` в `.importlinter` запрещает `collect` знать про
    `classify`, потому что классификация обязана быть бесплатной и
    переигрываемой на уже собранных данных. Пороги читает тот, кто и так знает
    оба слоя, — командная строка (а с Ф5 это будет обработчик запроса).

    Берётся **максимум** окон А и Б: покупаем одним размером, а считает каждая
    точка по своему окну. Разные размеры окон дали бы разную цену у двух
    запросов одного проекта и смету, которую нельзя объяснить одной строкой.
    """
    await seed_thresholds(session)
    thresholds = thresholds_of(await active_ruleset(session))
    windows = thresholds.windows
    return PointWindows(
        point_months=max(windows.point_a_months, windows.point_b_months),
        baseline_months=windows.pre_start_baseline_months,
    )


async def _collect(*, refresh: bool = False) -> int:
    async with get_sessionmaker()() as session:
        report = await collect_all(session, refresh=refresh, windows=await _point_windows(session))
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _stage2(*, refresh: bool = False) -> int:
    """Шаг 2 воронки по предварительным кандидатам.

    Кандидатов считает `funnel.preliminary_candidates` — грубый префильтр по
    росту трафика. С Ф3 сюда придёт результат классификации, и команда
    останется той же.
    """
    async with get_sessionmaker()() as session:
        projects = (await session.execute(select(Project))).scalars().all()
        candidates = await preliminary_candidates(
            session, [project.id for project in projects], source=config_source()
        )
        if not candidates:
            print("кандидатов нет: шаг 2 не нужен — за «плохих» дорогие метрики не платятся")
            return 0
        print(f"кандидатов: {len(candidates)} из {len(projects)}")
        report = await collect_stage2(
            session, candidates, refresh=refresh, windows=await _point_windows(session)
        )
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


def config_source() -> MetricSource:
    """Каким источником помечены точки текущего режима."""
    return MetricSource.LIVE if config.ahrefs.provider == "live" else MetricSource.FIXTURE


async def _case_data(*, refresh: bool = False) -> int:
    """Ступень кейса: докупить кривую позиций и стоимость трафика.

    Только тем, у кого кейс будет, — проектам с вердиктом `good` или `medium`
    по действующей версии порогов. «Плохие» и «данных не хватает» не стоят
    ничего: в этом и смысл ступени.
    """
    async with get_sessionmaker()() as session:
        stmt = (
            select(Verdict.project_id)
            .join(Ruleset, Ruleset.id == Verdict.ruleset_id)
            .where(Ruleset.is_active.is_(True), Verdict.group.in_([Group.GOOD, Group.MEDIUM]))
        )
        ids = list((await session.execute(stmt)).scalars().all())
        if not ids:
            print("кейсов нет: «хороших» и «средних» по действующим порогам не найдено")
            return 0
        print(f"проектов с кейсом: {len(ids)}")
        report = await collect_case_data(
            session, ids, refresh=refresh, windows=await _point_windows(session)
        )
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _classify() -> int:
    """Классификация по действующей версии порогов.

    Ahrefs не трогается: считаем по тому, что уже куплено. Если активной
    версии порогов нет — сеем её из `config/thresholds.example.yml`, потому
    что первый запуск на пустой базе иначе упирается в ошибку там, где
    достаточно дефолтов Приложения А.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        report = await classify_all(session)
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.total else 1


async def _recalc(version: str, *, make_active: bool) -> int:
    """Пересчёт по указанной версии порогов. Ahrefs не трогается.

    Нужен калибровке: заказчик правит пороги по десяти доменам с экспертной
    оценкой и смотрит, что изменилось. Прошлые вердикты остаются на месте —
    вопрос «почему тогда было good» обязан иметь ответ.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            if make_active:
                await activate(session, version)
            report = await recalc(session, version, source=config_source())
        except ThresholdsError as exc:
            print(f"пересчёт не выполнен: {exc}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.recalculated else 1


async def _preview(version: str) -> int:
    """Что даст версия порогов, если её применить. Ничего не меняет.

    Нужна калибровке: заказчик правит порог, смотрит последствия, спорит,
    правит снова. Отвечать на это записью вердиктов значит смотреть на уже
    изменённое и откатывать руками.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            report = await preview(session, version, source=config_source())
        except ThresholdsError as exc:
            print(f"предпросмотр не выполнен: {exc}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0


async def _diagnose(domain: str | None) -> int:
    """Диагностика «плохих»: что просело, когда началось, потеряны ли домены.

    По ТЗ кейс «плохим» не формируется, но список с краткой причиной нужен для
    внутреннего анализа. Ahrefs не трогается, в базу ничего не пишется.
    """
    async with get_sessionmaker()() as session:
        if domain is not None:
            one = await diagnose_domain(session, domain, source=config_source())
            if one is None:
                print(f"проект не найден: {domain}", file=sys.stderr)
                return _EXIT_BAD_SOURCE
            print("\n".join(one.as_lines()))
            return 0

        found = await diagnose_poor(session, source=config_source())
    if not found:
        print("«плохих» проектов нет — диагностировать нечего")
        return 0
    print(f"«плохих» проектов: {len(found)}")
    for item in found:
        print("\n".join(item.as_lines()))
    return 0


async def _explain(domain: str) -> int:
    """Показать вердикт одного домена со всеми условиями.

    Нужна не для отладки, а для калибровки: заказчик сверяет группу с
    экспертной оценкой и должен видеть, какое условие её определило.
    """
    async with get_sessionmaker()() as session:
        project = (
            (await session.execute(select(Project).where(Project.domain == domain)))
            .scalars()
            .first()
        )
        if project is None:
            print(f"проект не найден: {domain}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        ruleset = await active_ruleset(session)
        decision = await classify_project(session, project, ruleset)
        await session.commit()

    print(
        f"{domain}: {decision.group.value} (пороги {ruleset.version}, score {decision.score:.0f})"
    )
    for reason in decision.reasons:
        mark = "✓" if reason.passed else "✗"
        weight = "решает" if reason.decisive else "справочно"
        fact = "—" if reason.fact is None else f"{reason.fact:.1f}"
        threshold = "—" if reason.threshold is None else f"{reason.threshold:.1f}"
        print(
            f"  {mark} {reason.subject:34} факт {fact:>10}  порог {threshold:>10}  [{weight}] {reason.note}"
        )
    return 0


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
            return await _collect(refresh=args.refresh)
        if args.command == "stage2":
            return await _stage2(refresh=args.refresh)
        if args.command == "classify":
            return await _classify()
        if args.command == "case-data":
            return await _case_data(refresh=args.refresh)
        if args.command == "recalc":
            return await _recalc(args.version, make_active=args.activate)
        if args.command == "preview":
            return await _preview(args.version)
        if args.command == "cases":
            return await show_cases(args.domain, args.version)
        if args.command == "render":
            return await render_case(args.domain)
        if args.command == "pack":
            return await pack_cases()
        if args.command == "diagnose":
            return await _diagnose(args.domain)
        if args.command == "explain":
            return await _explain(args.domain)
        code = await _intake(args.source)
        return code or await _collect(refresh=args.refresh)
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
    sub.add_parser("pack", help="собрать кейсы «хороших» и «средних» в ZIP-архив")
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
