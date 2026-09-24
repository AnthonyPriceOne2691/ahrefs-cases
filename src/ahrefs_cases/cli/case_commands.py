"""Команды кейсов для командной строки: показать, собрать файл, собрать пачку.

Живут модулем, а не в скрипте, по прозаической причине: скрипт перевалил за
предел длины файла, и гейт был прав — в нём собрались четыре разные работы.
Слой тот же, что у `api` и `workers`: обвязка, которая знает про ядро, но не
наоборот. Печать и коды возврата — тоже её дело: ядро ничего не печатает.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TextIO

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases.builder import build_cases
from ahrefs_cases.cases.model import SUBJECT_LABELS, CaseData, CaseOutcome, CaseReport, Change
from ahrefs_cases.cases.stoplist import ContentBlockedError
from ahrefs_cases.cases.store import next_version, store_artifact, store_case
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.cli.source import reading_source
from ahrefs_cases.export.archive import EmptyArchiveError, Packed, SkippedCase, ToPack, pack
from ahrefs_cases.export.pdf_renderer import render_pdf
from ahrefs_cases.storage._enums import MetricSource, RunItemOutcome
from ahrefs_cases.storage.session import get_sessionmaker

EXIT_BAD_SOURCE = 2
EXIT_CONTENT_BLOCKED = 4
"""Коды возврата команд кейсов. У контент-запрета свой, потому что действие по
нему другое: править входной файл, а не искать поломку в логах."""


async def show_cases(
    domain: str | None, version: str | None, source: MetricSource | None = None
) -> int:
    """Показать, что соберётся в кейсы. Ничего не пишет, Ahrefs не трогает.

    Печатает **все четыре исхода**, включая нулевые: отсутствие строки человек
    читает как «таких не было», не отличив от «не проверяли» (L32, L34).
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            report = await build_cases(
                session, domain=domain, version=version, source=reading_source(source)
            )
        except ThresholdsError as exc:
            print(f"кейсы не собраны: {exc}", file=sys.stderr)
            return EXIT_BAD_SOURCE
        await session.commit()

    if not report.attempts:
        print("проектов нет: сначала `intake`, потом `collect` и `classify`")
        return 0
    print("\n".join(report.as_lines()))
    _print_refusals(report)
    for attempt in report.by_outcome(CaseOutcome.BUILT):
        if attempt.case is not None:
            print("")
            print("\n".join(_case_lines(attempt.domain, attempt.case)))
            if attempt.stale_subjects:
                missing = ", ".join(SUBJECT_LABELS[subject] for subject in attempt.stale_subjects)
                print(f"  куплено, но не в вердикте: {missing} — перезапустите `classify`")
    return 0


def _print_refusals(report: CaseReport, *, stream: TextIO = sys.stdout) -> None:
    """Домены, которым отказано из-за происхождения чисел, — с причиной.

    Печатается всегда, когда такие есть: счётчик в отчёте говорит «сколько», а
    человеку нужно «кому и почему». Молчаливый отказ здесь читается как
    поломка сборки, хотя это сработавшее правило.
    """
    for attempt in report.by_outcome(CaseOutcome.VERDICT_MISMATCH):
        print(f"{attempt.domain}: {attempt.detail}", file=stream)


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


async def render_case(domain: str, source: MetricSource | None = None) -> int:
    """Собрать кейс одного проекта и положить PDF на диск.

    Отдельный код возврата у контент-запрета (4), потому что действие по нему
    другое: не «смотреть логи», а править входной файл или не публиковать этот
    проект вовсе. Слить его с «прогон упал» значило бы отправить человека искать
    поломку там, где сработало правило.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        report = await build_cases(session, domain=domain, source=reading_source(source))

        if not report.attempts:
            print(f"проект не найден: {domain}", file=sys.stderr)
            return EXIT_BAD_SOURCE
        built = report.by_outcome(CaseOutcome.BUILT)
        if not built:
            print(f"кейс не собран — {report.attempts[0].outcome.value}", file=sys.stderr)
            print("\n".join(report.as_lines()), file=sys.stderr)
            _print_refusals(report, stream=sys.stderr)
            return EXIT_BAD_SOURCE

        for attempt in built:
            if attempt.case is None or attempt.project_id is None or attempt.verdict_id is None:
                continue
            # Номер сборки спрашивается ДО рисования, потому что он попал в имя
            # файла (решение владельца 15.09.2026). Это чтение, а не запись:
            # `store_case` ниже спросит то же число в той же транзакции.
            case = replace(attempt.case, version=await next_version(session, attempt.project_id))
            try:
                rendered = render_pdf(case)
            except ContentBlockedError as exc:
                print(f"{attempt.domain}: {exc}", file=sys.stderr)
                return EXIT_CONTENT_BLOCKED
            # Запись идёт после файла: кейса без артефакта в базе не бывает,
            # а артефакт без записи — просто файл, который можно пересобрать.
            case_row = await store_case(
                session,
                project_id=attempt.project_id,
                verdict_id=attempt.verdict_id,
                case=case,
            )
            artifact = await store_artifact(session, case_id=case_row.id, path=rendered.path)
            print(
                f"{attempt.domain} → {rendered.path} ({rendered.pages} стр.), "
                f"версия кейса {case_row.version}, sha256 {artifact.checksum[:12]}"
            )
        await session.commit()
    return 0


async def pack_cases(source: MetricSource | None = None) -> int:
    """Собрать кейсы всех «хороших» и «средних» в один архив.

    Отчёт печатает все исходы сборки и отдельно — кто не попал в архив по
    контент-запрету: «пропущено N» оставило бы человека без следующего шага
    (уроки L32 и L34).
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        result = await pack_built(session, reading_source(source))
        await session.commit()

    print("\n".join(result.report.as_lines()))
    _print_refusals(result.report)
    if result.bundle is None:
        print(result.empty, file=sys.stderr)
        return EXIT_BAD_SOURCE
    print("\n".join(result.bundle.as_lines()))
    return EXIT_CONTENT_BLOCKED if result.skipped else 0


@dataclass(frozen=True, slots=True)
class CasePack:
    """Сборка пачки целиком: исходы по проектам и архив, если он собрался.

    Одна на команду `pack` и на задачу очереди за кнопкой «Собрать кейсы»:
    команда её печатает, задача пишет в журнал прогона. Пока задача получала
    от сборки только код возврата, журнал говорил «собрано 0» при собранной
    пачке, а сводка жила в логе воркера (Z46, урок L130).
    """

    report: CaseReport
    bundle: Packed | None
    """`None` — архива нет: собирать было нечего."""

    skipped: tuple[SkippedCase, ...]
    """Не попали в архив по контент-запрету — и когда он собран, и когда нет."""

    empty: str = ""
    """Почему архива нет; пусто — архив есть."""

    def lines(self) -> list[str]:
        """Сводка для лога: исходы сборки, потом архив или почему его нет."""
        return [*self.report.as_lines(), *(self.bundle.as_lines() if self.bundle else [self.empty])]


async def pack_built(session: AsyncSession, source: MetricSource) -> CasePack:
    """Собрать кейсы, упаковать собранные и записать каждому его строку `cases`.

    В сессии вызывающего и без коммита: задача коммитит вместе со строками
    журнала прогона — одной транзакцией, чтобы записанный кейс и его судьба в
    журнале не разошлись.
    """
    report = await build_cases(session, source=source)
    try:
        bundle = await _pack_and_store(session, report)
    except EmptyArchiveError as exc:
        return CasePack(report=report, bundle=None, skipped=exc.skipped, empty=str(exc))
    return CasePack(report=report, bundle=bundle, skipped=bundle.skipped)


@dataclass(frozen=True, slots=True)
class CaseFate:
    """Судьба проекта в сборке кейсов — строка журнала прогона."""

    project_id: int
    domain: str
    outcome: RunItemOutcome
    reason: str


_QUIET_FATES: Mapping[CaseOutcome, tuple[RunItemOutcome, str]] = MappingProxyType(
    {
        CaseOutcome.NOT_ELIGIBLE: (
            RunItemOutcome.CASE_NOT_ELIGIBLE,
            "группа «плохой»: кейс по ТЗ собирают хорошим и средним",
        ),
        CaseOutcome.INSUFFICIENT_DATA: (
            RunItemOutcome.CASE_INSUFFICIENT_DATA,
            "группа «данных не хватает»: почему — в карточке проекта, «Почему эта группа»",
        ),
    }
)
"""Исходы, у которых причина одна на всех: её называет группа вердикта."""


def case_fates(result: CasePack) -> list[CaseFate]:
    """Судьба каждого рассмотренного проекта — исход и причина словами.

    Собранный кейс — `ok` с именем файла в пачке, собранный и не отданный —
    `case_blocked` с причиной запрета: оба ищутся по номеру проекта, домен у
    двух кампаний одного сайта один (Z39). У «вердикт не про эти данные» —
    объяснение и совет сборки (`builder._mismatch`).
    """
    packed = {one.project_id: one.arcname for one in result.bundle.packed} if result.bundle else {}
    blocked = {one.project_id: one.reason for one in result.skipped}
    version = result.report.ruleset_version
    fates: list[CaseFate] = []
    for attempt in result.report.attempts:
        pid = attempt.project_id
        if pid is None:
            continue
        if attempt.outcome is CaseOutcome.BUILT:
            outcome, reason = (
                (RunItemOutcome.OK, f"кейс собран: {packed[pid]}")
                if pid in packed
                else (RunItemOutcome.CASE_BLOCKED, blocked[pid])
            )
        elif attempt.outcome is CaseOutcome.NO_VERDICT:
            outcome = RunItemOutcome.CASE_NO_VERDICT
            reason = (
                f"нет вердикта по действующим порогам «{version}»: его вынесет сбор или пересчёт"
            )
        elif attempt.outcome is CaseOutcome.VERDICT_MISMATCH:
            outcome, reason = RunItemOutcome.CASE_VERDICT_MISMATCH, attempt.detail
        else:
            outcome, reason = _QUIET_FATES[attempt.outcome]
        fates.append(CaseFate(pid, attempt.domain, outcome, reason))
    return fates


async def _pack_and_store(session: AsyncSession, report: CaseReport) -> Packed:
    """Упаковать собранные кейсы и записать каждому проекту его строку и его файл.

    Ключ — проект, а не домен. У двух кампаний одного сайта домен один, и
    словарь номеров сборки, отказы запрета и поиск файла по домену отдавали
    обеим строкам `cases` числа и файл одной кампании: у `nordvpn.com` так
    было во всех сборках (Z39, класс урока L150). Строка пишется тем кейсом,
    что лёг в файл; проект, не попавший в архив (контент-запрет), строку не
    получает — причина уже в `Packed.skipped`.
    """
    verdicts: dict[int, int] = {}
    wanted: list[ToPack] = []
    for item in report.by_outcome(CaseOutcome.BUILT):
        if item.case is None or item.project_id is None or item.verdict_id is None:
            continue
        verdicts[item.project_id] = item.verdict_id
        # Номер сборки — до упаковки: он в имени файла внутри архива.
        version = await next_version(session, item.project_id)
        wanted.append(ToPack(item.project_id, item.domain, replace(item.case, version=version)))

    bundle = pack(wanted)
    for one in bundle.packed:
        case_row = await store_case(
            session, project_id=one.project_id, verdict_id=verdicts[one.project_id], case=one.case
        )
        await store_artifact(session, case_id=case_row.id, path=one.path)
    return bundle
