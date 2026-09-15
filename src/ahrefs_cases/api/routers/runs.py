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
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text

from ahrefs_cases.api.deps import SessionDep, UserDep, require_right
from ahrefs_cases.api.schemas import (
    MAX_PAGE,
    RunAuthor,
    RunCard,
    RunEstimate,
    RunItemView,
    RunRow,
    RunStarted,
)
from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.collect.budget import reserved_units, uncounted_spend
from ahrefs_cases.collect.factory import build_provider, build_quota
from ahrefs_cases.collect.plan import build_stage1_plan
from ahrefs_cases.collect.quota import preflight
from ahrefs_cases.collect.run_journal import fates as run_fates
from ahrefs_cases.collect.run_journal import open_run
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers.jobs import cases_job, collect_job
from ahrefs_cases.workers.queue import build_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])

ACTIVE_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)
MAX_FATES = 200
"""Потолок списка судеб: сто проектов прогона плюс запас. Граница нужна не от
жадности — у прогона столько проектов, сколько в списке заказчика, и выдача без
границы ломается ровно на большом прогоне (гейт `unbounded-list`)."""

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


DAY = timedelta(days=1)
"""Шаг верхней границы отбора: `until` включает весь названный день."""


@router.get("", response_model=list[RunRow])
async def list_runs(
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    started_by: Annotated[int | None, Query(ge=1)] = None,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
) -> list[RunRow]:
    """Журнал прогонов: свежие сверху, с именем того, кто запускал.

    Авторы берутся **одним запросом** на страницу, а не по строке: двадцать
    прогонов дали бы двадцать походов в базу за тем же десятком людей.

    Страницы и отборы заведены 15.09.2026: журнал на стенде перевалил за пять
    сотен строк, и «свежие двадцать» перестали отвечать на вопрос «а что было
    в понедельник и кто это запускал».

    Границы дат **включающие и по календарю**: `until=2026-09-13` берёт весь
    тринадцатое число, а не «до полуночи». Иначе человек, выбравший один день,
    получил бы пустой список и решил, что прогонов не было.
    """
    stmt = select(Run).order_by(Run.id.desc())
    if started_by is not None:
        stmt = stmt.where(Run.started_by == started_by)
    if since is not None:
        stmt = stmt.where(Run.created_at >= datetime.combine(since, time.min, tzinfo=UTC))
    if until is not None:
        stmt = stmt.where(Run.created_at < datetime.combine(until, time.min, tzinfo=UTC) + DAY)
    runs = list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())
    return [_row(run, await _authors(session, runs)) for run in runs]


@router.get("/authors", response_model=list[RunAuthor])
async def run_authors(
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = MAX_PAGE,
) -> list[RunAuthor]:
    """Кем запускались прогоны — для отбора в журнале.

    Отдельным путём, а не полем страницы: страница показывает двадцать строк, и
    список авторов, собранный по ней, менялся бы от страницы к странице — отбор
    «показать Петра» исчезал бы, стоило пролистнуть туда, где Петра нет.

    Объявлен **до** `/{run_id}`: иначе слово `authors` уходит в разбор номера
    (урок L173, тот же капкан, что у `pack` и `selection`).
    """
    # Потолок стоит, хотя авторов столько же, сколько заведённых людей: список
    # без границы — это обещание, что их всегда мало, а сервис живёт годами и
    # учётки в нём копятся. Гейт `unbounded-list` прав, и спорить с ним здесь
    # дешевле, чем однажды отдать страницу на тысячу строк.
    ids = (await session.execute(select(Run.started_by).distinct().limit(limit))).scalars().all()
    if not ids:
        return []
    users = (await session.execute(select(User).where(User.id.in_(set(ids))))).scalars().all()
    known = {user.id: user for user in users}
    return [
        RunAuthor(
            id=author_id,
            name=known[author_id].email if author_id in known else f"#{author_id}",
            deleted=author_id not in known or known[author_id].deleted_at is not None,
        )
        for author_id in sorted(set(ids))
    ]


async def _authors(session: SessionDep, runs: Sequence[Run]) -> dict[int, User]:
    """Учётки авторов прогонов, включая удалённые.

    Удалённые нужны именно здесь: строка учётки живёт ради этого журнала, и
    прятать её тут значило бы стереть ответ на вопрос «кто запускал».
    """
    ids = {run.started_by for run in runs}
    if not ids:
        return {}
    found = (await session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    return {user.id: user for user in found}


@router.get("/estimate", response_model=RunEstimate)
async def estimate_run(
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> RunEstimate:
    """Во что обойдётся прогон сбора и можно ли его начинать.

    Объявлен **выше** `/{run_id}` нарочно: FastAPI берёт первый подходящий
    маршрут, и ниже слово `estimate` уехало бы в целочисленный параметр,
    превратив смету в `422`.

    Смета считается **не открывая прогон**: строка прогона держит резерв units
    и попадает в чужую смету, а человек, посмотревший цену и передумавший,
    оставлял бы за собой отклонённый прогон в журнале. Ничего платного здесь не
    происходит — план строится по базе, а остаток квоты стоит 0 units.
    """
    projects = list((await session.execute(select(Project))).scalars().all())
    plan = await build_stage1_plan(
        session,
        projects,
        source=build_provider().source,
        now=date.today(),  # noqa: DTZ011 — календарная граница закрытого месяца
        windows=await point_windows(session),
    )
    estimate = plan.estimated_units()
    reserved = await reserved_units(session)
    state = await preflight(
        build_quota(),
        needed=estimate,
        reserved=reserved,
        uncounted=await uncounted_spend(session),
    )
    return RunEstimate(
        projects=len(projects),
        units_estimated=estimate,
        requests_planned=len(plan.tasks),
        requests_cached=len(plan.cached),
        scheme_lines=list(plan.scheme_breakdown().as_lines()),
        quota_left=state.left,
        quota_reserved=reserved,
        verdict=state.verdict.value,
        may_start=state.may_start,
        reason=state.reason,
    )


@router.get("/{run_id}", response_model=RunCard)
async def run_status(
    run_id: int,
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> RunCard:
    """Статус одного прогона и судьба каждого домена в нём.

    Судьбы здесь, а не отдельным адресом: «17 из 19» без остальных двух — это
    вопрос, который человек всё равно задаст следующим действием, и второй
    запрос ради него лишний.
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"прогона {run_id} нет")
    fates = await run_fates(session, run_id, limit=MAX_FATES)
    return RunCard(
        **_row(run).model_dump(),
        fates=[
            RunItemView(
                domain=fate.domain,
                outcome=fate.outcome.value,
                reason=fate.reason,
                units_actual=fate.units_actual,
            )
            for fate in fates
        ],
    )


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


def _row(run: Run, authors: Mapping[int, User] | None = None) -> RunRow:
    author = (authors or {}).get(run.started_by)
    return RunRow(
        id=run.id,
        status=run.status.value,
        started_by=run.started_by,
        # Имя, а если его не заполняли — почта: «Прогон из командной строки»
        # человеку говорит больше, чем `cli@local`, но пустая строка — ничего.
        started_by_name=(author.full_name or author.email) if author else "",
        started_by_deleted=bool(author and author.deleted_at is not None),
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
    )
