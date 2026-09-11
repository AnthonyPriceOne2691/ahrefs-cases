"""Команды кейсов для командной строки: показать, собрать файл, собрать пачку.

Живут модулем, а не в скрипте, по прозаической причине: скрипт перевалил за
предел длины файла, и гейт был прав — в нём собрались четыре разные работы.
Слой тот же, что у `api` и `workers`: обвязка, которая знает про ядро, но не
наоборот. Печать и коды возврата — тоже её дело: ядро ничего не печатает.
"""

from __future__ import annotations

import sys

from ahrefs_cases.cases.builder import build_cases
from ahrefs_cases.cases.model import SUBJECT_LABELS, CaseData, CaseOutcome, Change
from ahrefs_cases.cases.stoplist import ContentBlockedError
from ahrefs_cases.cases.store import store_artifact, store_case
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.export.archive import EmptyArchiveError, pack
from ahrefs_cases.export.pdf_renderer import render_pdf
from ahrefs_cases.storage._enums import MetricSource
from ahrefs_cases.storage.session import get_sessionmaker

EXIT_BAD_SOURCE = 2
EXIT_CONTENT_BLOCKED = 4
"""Коды возврата команд кейсов. У контент-запрета свой, потому что действие по
нему другое: править входной файл, а не искать поломку в логах."""


def _source() -> MetricSource:
    """Откуда брать серии. Совпадает с выбором провайдера в конфиге."""
    from ahrefs_cases import config

    return MetricSource.LIVE if config.ahrefs.provider == "live" else MetricSource.FIXTURE


async def show_cases(domain: str | None, version: str | None) -> int:
    """Показать, что соберётся в кейсы. Ничего не пишет, Ahrefs не трогает.

    Печатает **все четыре исхода**, включая нулевые: отсутствие строки человек
    читает как «таких не было», не отличив от «не проверяли» (L32, L34).
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            report = await build_cases(session, domain=domain, version=version, source=_source())
        except ThresholdsError as exc:
            print(f"кейсы не собраны: {exc}", file=sys.stderr)
            return EXIT_BAD_SOURCE
        await session.commit()

    if not report.attempts:
        print("проектов нет: сначала `intake`, потом `collect` и `classify`")
        return 0
    print("\n".join(report.as_lines()))
    for attempt in report.by_outcome(CaseOutcome.BUILT):
        if attempt.case is not None:
            print("")
            print("\n".join(_case_lines(attempt.domain, attempt.case)))
            if attempt.stale_subjects:
                missing = ", ".join(SUBJECT_LABELS[subject] for subject in attempt.stale_subjects)
                print(f"  куплено, но не в вердикте: {missing} — перезапустите `classify`")
    return 0


def _case_lines(domain: str, case: CaseData) -> list[str]:
    """Кейс одной карточкой. Анонимность защищает артефакт, а не консоль:
    оператору нужен и домен, и то, каким кейс уйдёт наружу."""
    head = f"{domain} — {case.group.value}, {case.period.months} мес., {case.geo} / {case.niche}"
    if case.anonymized:
        head += f" [анонимно: «{case.title}»]"
    lines = [head]
    if case.work_volume is not None:
        lines.append(f"  что сделали: {case.work_volume}")
    lines.extend(f"  {_change_line(change)}" for change in case.changes)
    return lines


def _change_line(change: Change) -> str:
    growth = "с нуля" if change.pct is None else f"{change.pct:+.0f} %"
    return f"{change.label:32} {change.before:>10.0f} → {change.after:>10.0f}  ({growth})"


async def render_case(domain: str) -> int:
    """Собрать кейс одного проекта и положить PDF на диск.

    Отдельный код возврата у контент-запрета (4), потому что действие по нему
    другое: не «смотреть логи», а править входной файл или не публиковать этот
    проект вовсе. Слить его с «прогон упал» значило бы отправить человека искать
    поломку там, где сработало правило.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        report = await build_cases(session, domain=domain, source=_source())

        if not report.attempts:
            print(f"проект не найден: {domain}", file=sys.stderr)
            return EXIT_BAD_SOURCE
        built = report.by_outcome(CaseOutcome.BUILT)
        if not built:
            print(f"кейс не собран — {report.attempts[0].outcome.value}", file=sys.stderr)
            print("\n".join(report.as_lines()), file=sys.stderr)
            return EXIT_BAD_SOURCE

        for attempt in built:
            if attempt.case is None or attempt.project_id is None or attempt.verdict_id is None:
                continue
            try:
                rendered = render_pdf(attempt.case)
            except ContentBlockedError as exc:
                print(f"{attempt.domain}: {exc}", file=sys.stderr)
                return EXIT_CONTENT_BLOCKED
            # Запись идёт после файла: кейса без артефакта в базе не бывает,
            # а артефакт без записи — просто файл, который можно пересобрать.
            case_row = await store_case(
                session,
                project_id=attempt.project_id,
                verdict_id=attempt.verdict_id,
                case=attempt.case,
            )
            artifact = await store_artifact(session, case_id=case_row.id, path=rendered.path)
            print(
                f"{attempt.domain} → {rendered.path} ({rendered.pages} стр.), "
                f"версия кейса {case_row.version}, sha256 {artifact.checksum[:12]}"
            )
        await session.commit()
    return 0


async def pack_cases() -> int:
    """Собрать кейсы всех «хороших» и «средних» в один архив.

    Отчёт печатает четыре исхода сборки и отдельно — кто не попал в архив по
    контент-запрету: «пропущено N» оставило бы человека без следующего шага
    (уроки L32 и L34).
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        report = await build_cases(session, source=_source())
        built = [item for item in report.by_outcome(CaseOutcome.BUILT) if item.case is not None]
        print("\n".join(report.as_lines()))

        try:
            bundle = pack([(item.domain, item.case) for item in built if item.case])
        except EmptyArchiveError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_BAD_SOURCE

        blocked = {item.domain for item in bundle.skipped}
        for item in built:
            if item.case is None or item.domain in blocked:
                continue
            if item.project_id is None or item.verdict_id is None:
                continue
            case_row = await store_case(
                session, project_id=item.project_id, verdict_id=item.verdict_id, case=item.case
            )
            path = next(one.path for one in bundle.packed if one.domain == item.domain)
            await store_artifact(session, case_id=case_row.id, path=path)
        await session.commit()

    print("\n".join(bundle.as_lines()))
    return EXIT_CONTENT_BLOCKED if bundle.skipped else 0
