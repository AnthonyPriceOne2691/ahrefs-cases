"""Строка журнала прогонов: итоги, режим, пачка и цепочка — одним местом.

Вынесено из `api/routers/runs.py`, когда тот перерос планку длины: журнал
(`GET /api/runs`) и карточка прогона (`GET /api/runs/{id}`) строят строку одной
функцией, и признаки, которые считаются по всему журналу («последний без
сборки после», «цепочка пойдёт дальше»), собираются здесь же — один раз на
страницу, а не на строку.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.schemas import RunRow
from ahrefs_cases.collect.run_journal import CASE_DATA, CASES, CHAIN
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User

FINISHED = frozenset({RunStatus.DONE, RunStatus.PARTIAL})


async def offers_build(session: AsyncSession) -> int:
    """Номер прогона, предлагающего «Собрать кейсы», — или 0.

    Это последний «данные под кейс», и только если он закончился, а сборки
    после него не было: после сборки следующий шаг — «Скачать» у неё самой.
    Считается по всем прогонам, а не по странице журнала: страница может
    кончиться раньше, чем найдётся более поздняя сборка.
    """
    stage = Run.params_snapshot["stage"].astext
    stmt = select(stage, func.max(Run.id)).where(stage.in_((CASE_DATA, CASES))).group_by(stage)
    last: dict[str, int] = dict((await session.execute(stmt)).tuples().all())
    data = last.get(CASE_DATA, 0)
    if not data or data < last.get(CASES, 0):
        return 0
    run = await session.get(Run, data)
    return data if run is not None and run.status in FINISHED else 0


CHAIN_GAP = timedelta(minutes=2)
"""Сколько после конца ступени цепочки ждать следующую. Ступени идут одна за
другой без пауз — щель в миллисекунды, у данных под кейс — пересчёт групп,
секунды. Две минуты без следующей строки значат, что цепочка кончилась или
её задачу убили (выкатка): экрану пора перестать опрашивать."""


@dataclass(frozen=True, slots=True)
class Journal:
    """Что строке журнала нужно знать о журнале целиком."""

    offers: int = 0
    """Номер прогона, предлагающего «Собрать кейсы» (`_offers_build`)."""

    chain_keys: frozenset[str] = frozenset()
    """Ключи задач цепочек среди строк страницы."""

    newest: int = 0
    now: datetime | None = None


async def journal_context(session: AsyncSession, runs: Sequence[Run]) -> Journal:
    """Сведения о журнале для строк страницы: три запроса на страницу, а не на строку.

    Цепочка узнаётся по ключу задачи: «данные под кейс» открывает `_stage2` без
    метки цепочки, но с её ключом (`run_journal.CHAIN`).
    """
    keys = {str(key) for run in runs if (key := (run.params_snapshot or {}).get("job"))}
    chain_keys: frozenset[str] = frozenset()
    if keys:
        job = Run.params_snapshot["job"].astext
        marked = Run.params_snapshot[CHAIN].astext == "true"
        stmt = select(job).where(job.in_(keys), marked).distinct()
        chain_keys = frozenset((await session.execute(stmt)).scalars())
    return Journal(
        offers=await offers_build(session),
        chain_keys=chain_keys,
        newest=int(await session.scalar(select(func.max(Run.id))) or 0),
        now=datetime.now(UTC),
    )


def chain_state(run: Run, journal: Journal) -> tuple[bool, bool]:
    """Ступень ли это цепочки и пойдёт ли цепочка дальше."""
    snapshot = run.params_snapshot or {}
    chain = bool(snapshot.get(CHAIN)) or str(snapshot.get("job") or "") in journal.chain_keys
    continues = (
        chain
        and run.id == journal.newest
        and snapshot.get("stage") != CASES
        and run.status in FINISHED
        and run.finished_at is not None
        and journal.now is not None
        and journal.now - run.finished_at < CHAIN_GAP
    )
    return chain, continues


def run_row(
    run: Run,
    authors: Mapping[int, User] | None = None,
    live: Collection[int] = (),
    journal: Journal | None = None,
) -> RunRow:
    author = (authors or {}).get(run.started_by)
    cases = (run.params_snapshot or {}).get("pack_cases")
    context = journal or Journal()
    chain, continues = chain_state(run, context)
    return RunRow(
        id=run.id,
        status=run.status.value,
        started_by=run.started_by,
        # Имя, а если его не заполняли — почта: «Прогон из командной строки»
        # человеку говорит больше, чем `cli@local`, но пустая строка — ничего.
        started_by_name=(author.full_name or author.email) if author else "",
        started_by_deleted=bool(author and author.deleted_at is not None),
        stage=str((run.params_snapshot or {}).get("stage") or ""),
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        projects_total=run.projects_total,
        projects_ok=run.projects_ok,
        projects_failed=run.projects_failed,
        projects_skipped=max(0, run.projects_total - run.projects_ok - run.projects_failed),
        units_estimated=run.units_estimated,
        units_actual=run.units_actual,
        error=run.error,
        live=run.id in live,
        mode=str((run.params_snapshot or {}).get("provider") or ""),
        pack=bool((run.params_snapshot or {}).get("pack")),
        pack_cases=cases if isinstance(cases, int) else 0,
        chain=chain,
        continues=continues,
        build_cases=run.id == context.offers,
    )
