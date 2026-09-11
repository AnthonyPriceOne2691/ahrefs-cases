"""Запуск прогона, журнал и статус.

Прогон не выполняется в обработчике: сбор сотни доменов длиннее любого разумного
таймаута, а оборванный запрос заставит нажать ещё раз — за вторую цену в units.
Обработчик создаёт строку прогона (только он знает, **кто** нажал) и ставит
задачу в очередь.

**Замок на второй прогон — про деньги.** Запускают шесть-семь человек из четырёх
отделов по одному и тому же списку; второй прогон стоит вторую цену, а
склейка одинаковых запросов (`SingleFlightProvider`) живёт внутри процесса и
между прогонами не помогает.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text

from ahrefs_cases.api.deps import SessionDep, UserDep, require_right
from ahrefs_cases.api.schemas import MAX_PAGE, RunRow, RunStarted
from ahrefs_cases.collect.run_journal import open_run
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.workers.jobs import cases_job, collect_job
from ahrefs_cases.workers.queue import build_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])

ACTIVE_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)
_START_LOCK_KEY = 4_242_001
"""Ключ блокировки Postgres на время постановки прогона.

Проверка «нет активных» и создание строки обязаны быть неделимыми: между ними
помещается второй запрос, и тогда замок пропускает оба прогона. Советующая
блокировка транзакции дешевле таблицы-семафора и умирает вместе с транзакцией —
даже если процесс убьют.
"""


@router.post("", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
    refresh: bool = False,
) -> RunStarted:
    """Поставить прогон сбора в очередь. Активный прогон один."""
    return await _enqueue(session, user.id, job=collect_job, refresh=refresh)


@router.post("/cases", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_cases(
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
) -> RunStarted:
    """Поставить сборку пачки кейсов: тот же замок, та же очередь."""
    return await _enqueue(session, user.id, job=cases_job)


@router.get("", response_model=list[RunRow])
async def list_runs(
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 20,
) -> list[RunRow]:
    """Журнал прогонов: свежие сверху."""
    stmt = select(Run).order_by(Run.id.desc()).limit(limit)
    return [_row(run) for run in (await session.execute(stmt)).scalars().all()]


@router.get("/{run_id}", response_model=RunRow)
async def run_status(
    run_id: int,
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> RunRow:
    """Статус одного прогона — то, что опрашивает экран."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"прогона {run_id} нет")
    return _row(run)


async def _enqueue(
    session: SessionDep,
    user_id: int,
    *,
    job: Callable[..., object],
    refresh: bool = False,
) -> RunStarted:
    """Создать прогон под замком и поставить задачу."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _START_LOCK_KEY})
    active = (
        (await session.execute(select(Run).where(Run.status.in_(ACTIVE_STATUSES)).limit(1)))
        .scalars()
        .first()
    )
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"прогон {active.id} ещё идёт ({active.status.value}); второй не запускается",
        )

    total = int(await session.scalar(select(func.count()).select_from(Project)) or 0)
    run = await open_run(session, started_by=user_id, projects_total=total)
    await session.commit()

    queue = build_queue()
    queued_as = (
        await queue.enqueue(job, run.id, refresh) if refresh else await queue.enqueue(job, run.id)
    )
    logger.info("run_enqueued", extra={"run_id": run.id, "queued_as": queued_as})
    return RunStarted(run_id=run.id, queued_as=queued_as)


def _row(run: Run) -> RunRow:
    return RunRow(
        id=run.id,
        status=run.status.value,
        started_by=run.started_by,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        projects_total=run.projects_total,
        projects_ok=run.projects_ok,
        projects_failed=run.projects_failed,
        units_estimated=run.units_estimated,
        units_actual=run.units_actual,
        error=run.error,
    )
