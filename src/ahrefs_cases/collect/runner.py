"""Исполнение прогона: задачи → серии в базе, журнал и расход units.

Что здесь есть в Ф2а: параллельность с ограничением, штатные пропуски, журнал,
запись точек. Чего нет намеренно: кэша закрытых месяцев, инкрементального
`date_from` и single-flight — это Ф2б. Сейчас прогон запрашивает всё честно и
дорого, и разницу Ф2б предъявит числом из того же журнала.

Ошибка одного домена не останавливает прогон. Останавливать сотню доменов из-за
одного — то же самое, что не собрать ничего, а причина остаётся в `RunItem`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsHTTPError, AhrefsUnavailableError
from ahrefs_cases.collect.budget import record_spend, run_spend
from ahrefs_cases.collect.factory import build_provider
from ahrefs_cases.collect.plan import CollectTask, plan_stage1
from ahrefs_cases.collect.provider import AhrefsProvider, HistoryResult
from ahrefs_cases.collect.run_journal import add_item, finish_run, open_run, system_user
from ahrefs_cases.collect.series import store_history
from ahrefs_cases.storage._enums import ProjectStatus, RunItemOutcome
from ahrefs_cases.storage.models.project import Project

logger = logging.getLogger(__name__)

SHORT_HISTORY_POINTS = 6
"""Ниже этого числа месяцев история считается короткой и помечается в `RunItem`.

Пометка, а не пропуск: годится ли такая история для кейса, решает классификация
(Ф3) по порогам Приложения А — у сбора нет ни порогов, ни права их применять.
Сбор обязан только не молчать об этом.
"""


@dataclass(frozen=True, slots=True)
class RunReport:
    """Итог прогона в числах, которые показывают человеку."""

    run_id: int
    status: str
    projects_total: int
    projects_ok: int
    projects_skipped: int
    projects_failed: int
    points_written: int
    units_spent: int

    def as_lines(self) -> list[str]:
        return [
            f"прогон {self.run_id}: {self.status}",
            f"проектов: {self.projects_total} "
            f"(собрано {self.projects_ok}, пропущено {self.projects_skipped}, "
            f"упало {self.projects_failed})",
            f"точек записано: {self.points_written}",
            f"units потрачено: {self.units_spent}",
        ]


@dataclass(slots=True)
class _TaskOutcome:
    """Что вышло по одной задаче. Складывается в журнал одним местом ниже."""

    task: CollectTask
    outcome: RunItemOutcome
    reason: str = ""
    result: HistoryResult | None = None


async def collect_projects(
    session: AsyncSession,
    projects: Sequence[Project],
    provider: AhrefsProvider | None = None,
) -> RunReport:
    """Собрать шаг 1 по списку проектов. Провайдер — из конфига, если не задан."""
    engine = provider or build_provider()
    user = await system_user(session)
    run = await open_run(session, started_by=user.id, projects_total=len(projects))
    tasks = plan_stage1(projects)

    outcomes = await _run_tasks(engine, tasks)

    points = 0
    for item in outcomes:
        if item.result is not None:
            points += await store_history(session, item.task.project_id, item.result)
            await record_spend(session, run.id, item.result)
        await add_item(
            session,
            run,
            project_id=item.task.project_id,
            raw_domain=item.task.domain,
            outcome=item.outcome,
            reason=item.reason,
            units_actual=item.result.units_actual if item.result else 0,
        )
    await _mark_projects(session, outcomes)
    await finish_run(session, run)

    return RunReport(
        run_id=run.id,
        status=run.status.value,
        projects_total=run.projects_total,
        projects_ok=run.projects_ok,
        projects_skipped=sum(
            1 for item in outcomes if item.outcome is RunItemOutcome.SKIPPED_NO_DATA
        ),
        projects_failed=run.projects_failed,
        points_written=points,
        units_spent=await run_spend(session, run.id),
    )


async def collect_all(session: AsyncSession, provider: AhrefsProvider | None = None) -> RunReport:
    """Прогон по всем проектам в базе — то, что делает CLI."""
    projects = (await session.execute(select(Project))).scalars().all()
    return await collect_projects(session, list(projects), provider)


async def _run_tasks(provider: AhrefsProvider, tasks: Sequence[CollectTask]) -> list[_TaskOutcome]:
    """Задачи параллельно, но не все сразу.

    Ограничение — из конфига (`COLLECT_MAX_PARALLEL`, по умолчанию 3): у Ahrefs
    есть лимит запросов в минуту, и сотня одновременных запросов приводит к 429
    по всем сразу, то есть к прогону, который стоит units и не приносит данных.
    """
    semaphore = asyncio.Semaphore(config.ahrefs.max_parallel)

    async def one(task: CollectTask) -> _TaskOutcome:
        async with semaphore:
            return await _fetch_one(provider, task)

    return list(await asyncio.gather(*(one(task) for task in tasks)))


async def _fetch_one(provider: AhrefsProvider, task: CollectTask) -> _TaskOutcome:
    """Один запрос. Исключение здесь — исход задачи, а не конец прогона."""
    try:
        result = await provider.fetch_history(task.spec, task.request)
    except (AhrefsUnavailableError, AhrefsHTTPError) as exc:
        logger.warning(
            "collect_task_failed",
            extra={"domain": task.domain, "endpoint": task.spec.name, "reason": str(exc)},
        )
        return _TaskOutcome(task=task, outcome=RunItemOutcome.FAILED, reason=str(exc))

    if result.is_empty:
        return _TaskOutcome(
            task=task,
            outcome=RunItemOutcome.SKIPPED_NO_DATA,
            reason="Ahrefs не отдал историю по домену",
            result=result,
        )

    months = len(result.points)
    reason = f"short_history: {months} мес." if months < SHORT_HISTORY_POINTS else ""
    return _TaskOutcome(task=task, outcome=RunItemOutcome.OK, reason=reason, result=result)


async def _mark_projects(session: AsyncSession, outcomes: Sequence[_TaskOutcome]) -> None:
    """Статус проекта по исходу сбора.

    Статус двигает прогон, а не приём списка (см. `intake/upsert.py`): иначе
    повторная загрузка файла обнуляла бы результат последнего сбора.
    """
    by_outcome = {
        RunItemOutcome.OK: ProjectStatus.COLLECTED,
        RunItemOutcome.SKIPPED_NO_DATA: ProjectStatus.SKIPPED,
        RunItemOutcome.FAILED: ProjectStatus.FAILED,
    }
    for item in outcomes:
        status = by_outcome.get(item.outcome)
        if status is None:
            continue
        project = await session.get(Project, item.task.project_id)
        if project is not None:
            project.status = status
