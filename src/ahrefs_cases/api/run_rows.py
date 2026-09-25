"""Строка журнала прогонов: итоги, режим, пачка и цикл по файлу — одним местом.

Вынесено из `api/routers/runs.py`, когда тот перерос планку длины: журнал
(`GET /api/runs`) и карточка прогона (`GET /api/runs/{id}`) строят строку одной
функцией, и признаки, которые считаются по всему журналу («последний без
сборки после», «какая ступень цикла идёт»), собираются здесь же — один раз на
страницу, а не на строку.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ahrefs_cases.api.schemas import RunRow
from ahrefs_cases.collect.run_journal import CASE_DATA, CASES, CYCLE
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


@dataclass(frozen=True, slots=True)
class CycleState:
    """Строка цикла по файлу, пока он идёт: какая ступень и сколько ушло units."""

    stage: str = ""
    units: int = 0


@dataclass(frozen=True, slots=True)
class Journal:
    """Что строке журнала нужно знать о журнале целиком."""

    offers: int = 0
    """Номер прогона, предлагающего «Собрать кейсы» (`offers_build`)."""

    cycles: Mapping[int, CycleState] = field(default_factory=dict)
    """Строки циклов на странице — по номеру строки цикла."""


async def journal_context(session: AsyncSession, runs: Sequence[Run]) -> Journal:
    """Сведения о журнале для строк страницы: по запросу на страницу, а не на строку.

    Ступени цикла в журнале не видны, их видит строка цикла: какая идёт сейчас
    и сколько units уже ушло. Узнаются они по общему ключу задачи
    (`run_journal.cycle_children`), одним запросом на все циклы страницы.
    """
    cycles = {
        str(key): run.id
        for run in runs
        if (run.params_snapshot or {}).get("stage") == CYCLE
        and (key := (run.params_snapshot or {}).get("job"))
    }
    states: dict[int, CycleState] = {}
    if cycles:
        job = Run.params_snapshot["job"].astext
        stmt = (
            select(job, Run.params_snapshot["stage"].astext, Run.units_actual)
            .where(job.in_(list(cycles)), Run.id.not_in(list(cycles.values())))
            .order_by(Run.id)
        )
        for key, stage, units in (await session.execute(stmt)).tuples():
            parent = cycles[str(key)]
            before = states.get(parent, CycleState())
            states[parent] = CycleState(stage=str(stage or ""), units=before.units + units)
    return Journal(offers=await offers_build(session), cycles=states)


def hide_cycle_steps() -> ColumnElement[bool]:
    """Условие журнала: ступени циклов не показываются отдельными строками.

    Ступень — прогон с ключом задачи строки цикла, но не она сама. Метки
    «чей я ребёнок» у ступеней нет (`run_journal.cycle_children`), поэтому
    вопрос задаётся к ключу.
    """
    parent = aliased(Run)
    step = exists().where(
        parent.params_snapshot["stage"].astext == CYCLE,
        parent.params_snapshot["job"].astext == Run.params_snapshot["job"].astext,
        parent.id != Run.id,
    )
    return ~step


def run_row(
    run: Run,
    authors: Mapping[int, User] | None = None,
    live: Collection[int] = (),
    journal: Journal | None = None,
) -> RunRow:
    author = (authors or {}).get(run.started_by)
    cases = (run.params_snapshot or {}).get("pack_cases")
    context = journal or Journal()
    cycle = context.cycles.get(run.id, CycleState())
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
        # У цикла units — сумма его ступеней: пока он идёт, своих у него нет.
        units_actual=max(run.units_actual, cycle.units),
        error=run.error,
        live=run.id in live,
        mode=str((run.params_snapshot or {}).get("provider") or ""),
        pack=bool((run.params_snapshot or {}).get("pack")),
        pack_cases=cases if isinstance(cases, int) else 0,
        current_stage=cycle.stage,
        build_cases=run.id == context.offers,
    )
