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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from uuid import uuid4

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, UserDep, require_right
from ahrefs_cases.api.run_estimates import cycle_estimate, estimate_view
from ahrefs_cases.api.run_rows import hide_cycle_steps, journal_context, run_row
from ahrefs_cases.api.schemas import (
    MAX_PAGE,
    CycleStart,
    RunAuthor,
    RunCard,
    RunEstimate,
    RunItemView,
    RunRow,
    RunStarted,
)
from ahrefs_cases.classify.candidates import stage2_candidates
from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.collect.budget import live_runs
from ahrefs_cases.collect.factory import build_provider
from ahrefs_cases.collect.plan import build_case_plan, build_stage1_plan, build_stage2_plan
from ahrefs_cases.collect.run_journal import (
    CASES,
    CYCLE,
    STAGE1,
    STAGE2,
    ProjectFate,
    cycle_children,
    open_run,
)
from ahrefs_cases.collect.run_journal import fates as run_fates
from ahrefs_cases.export.archive import run_pack_path
from ahrefs_cases.export.removal import holds_deleted_case
from ahrefs_cases.intake.normalize import to_unicode
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.locks import hold_start
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers.jobs import cases_job, chain_job, collect_job, stage2_job
from ahrefs_cases.workers.queue import build_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])

ACTIVE_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)
MAX_FATES = 200
"""Потолок списка судеб: сто проектов прогона плюс запас. Граница нужна не от
жадности — у прогона столько проектов, сколько в списке заказчика, и выдача без
границы ломается ровно на большом прогоне (гейт `unbounded-list`)."""


@router.post("", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
    refresh: bool = False,
) -> RunStarted:
    """Поставить прогон сбора в очередь. Активный прогон один."""
    return await _enqueue(session, user.id, job=collect_job, stage=STAGE1, refresh=refresh)


@router.post("/stage2", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_stage2(
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
) -> RunStarted:
    """Шаг 2 по кандидатам и данные под кейс — вторая кнопка, тот же замок (B6)."""
    return await _enqueue(session, user.id, job=stage2_job, stage=STAGE2)


@router.post("/cases", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_cases(
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
) -> RunStarted:
    """Поставить сборку пачки кейсов: тот же замок, та же очередь."""
    return await _enqueue(session, user.id, job=cases_job, stage=CASES)


@router.post("/chain", response_model=RunStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_cycle(
    body: CycleStart,
    session: SessionDep,
    user: UserDep,
    _: Annotated[object, Depends(require_right("run"))] = None,
) -> RunStarted:
    """Цикл по проектам файла одной кнопкой (решение владельца 25.09.2026).

    Одна строка журнала на весь цикл; ступени идут сами. Не хватает units на
    весь цикл по верхней границе — отказ до открытия прогона: «если юнитов
    мало и не хватит на полный цикл, то просто не давать запускать».
    """
    estimate = await cycle_estimate(session, body.project_ids)
    if not estimate.projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="проектов этого списка в базе нет — загрузите список заново",
        )
    if not estimate.may_start:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"на весь цикл не хватает units: нужно до {estimate.units_estimated}, "
            f"{estimate.reason or 'смета не пускает'}",
        )
    return await _enqueue(
        session,
        user.id,
        job=chain_job,
        stage=CYCLE,
        cycle=Cycle(projects=list(dict.fromkeys(body.project_ids)), units=estimate.units_estimated),
    )


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
    stmt = select(Run).where(hide_cycle_steps()).order_by(Run.id.desc())
    if started_by is not None:
        stmt = stmt.where(Run.started_by == started_by)
    if since is not None:
        stmt = stmt.where(Run.created_at >= datetime.combine(since, time.min, tzinfo=UTC))
    if until is not None:
        stmt = stmt.where(Run.created_at < datetime.combine(until, time.min, tzinfo=UTC) + DAY)
    runs = list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())
    authors, live = await _authors(session, runs), await live_runs(session, [r.id for r in runs])
    journal = await journal_context(session, runs)
    return [run_row(run, authors, live, journal) for run in runs]


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
    return await estimate_view(
        session,
        projects=len(projects),
        units=plan.estimated_units(),
        planned=len(plan.tasks),
        cached=len(plan.cached),
        lines=list(plan.scheme_breakdown().as_lines()),
    )


@router.get("/stage2/estimate", response_model=RunEstimate)
async def estimate_stage2(
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> RunEstimate:
    """Во что обойдётся вторая кнопка: шаг 2 по кандидатам и данные под кейс.

    Кандидаты к этому моменту известны — их выбирают действующие пороги по
    данным шага 1, — поэтому шаг 2 посчитан точно. Данные под кейс нужны тем,
    кто после шага 2 станет хорошим или средним, а это выяснится только после
    него: здесь они посчитаны по всем кандидатам, это верхняя граница, и она
    так и подписана. `projects` в ответе — число кандидатов.
    """
    windows = await point_windows(session)
    source = build_provider().source
    projects = list((await session.execute(select(Project))).scalars().all())
    wanted = set(await stage2_candidates(session, projects, source=source))
    chosen = [project for project in projects if project.id in wanted]
    today = date.today()  # noqa: DTZ011 — календарная граница закрытого месяца
    second = await build_stage2_plan(session, chosen, source=source, now=today, windows=windows)
    case = await build_case_plan(session, chosen, source=source, now=today, windows=windows)
    lines = [*second.scheme_breakdown().as_lines(), *case.scheme_breakdown().as_lines()]
    if chosen:
        lines.append(
            "данные под кейс посчитаны по всем кандидатам — это верхняя граница: "
            "докупаются только тем, кто после шага 2 станет хорошим или средним"
        )
    return await estimate_view(
        session,
        projects=len(chosen),
        units=second.estimated_units() + case.estimated_units(),
        planned=len(second.tasks) + len(case.tasks),
        cached=len(second.cached) + len(case.cached),
        lines=lines,
    )


@router.get("/chain/estimate", response_model=RunEstimate)
async def estimate_cycle(
    session: SessionDep,
    projects: Annotated[list[int], Query(min_length=1, max_length=1000)],
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> RunEstimate:
    """Смета цикла по проектам файла — то, что экран показывает после загрузки."""
    return await cycle_estimate(session, projects)


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
    fates = await _card_fates(session, run)
    return RunCard(
        **run_row(
            run,
            live=await live_runs(session, [run.id]),
            journal=await journal_context(session, [run]),
        ).model_dump(),
        fates=[
            RunItemView(
                # Журнал хранит канон — его отправили в Ahrefs; человек читает
                # домен так, как пишет его сам (правило 4а, то же, что у кейса).
                domain=to_unicode(fate.domain),
                outcome=fate.outcome.value,
                reason=fate.reason,
                units_actual=fate.units_actual,
                project_deleted=fate.project_deleted,
                stage=stage,
            )
            for stage, fate in fates
        ],
    )


async def _card_fates(session: AsyncSession, run: Run) -> list[tuple[str, ProjectFate]]:
    """Судьбы прогона, а у строки цикла — судьбы всех его ступеней с их ступенью."""
    if (run.params_snapshot or {}).get("stage") != CYCLE:
        return [("", fate) for fate in await run_fates(session, run.id, limit=MAX_FATES)]
    found: list[tuple[str, ProjectFate]] = []
    for child in await cycle_children(session, run):
        stage = str((child.params_snapshot or {}).get("stage") or "")
        found += [(stage, fate) for fate in await run_fates(session, child.id, limit=MAX_FATES)]
    return found


RUN_PACK_OF_DELETED = (
    "в пачке этого прогона кейс удалённого проекта — её больше не отдаём; "
    "соберите кейсы заново, и новая пачка соберётся без него"
)
"""Почему копию пачки прогона не отдают — то же правило, что у пачки дня."""


@router.get("/{run_id}/pack")
async def download_run_pack(
    run_id: int,
    session: SessionDep,
    _: Annotated[object, Depends(require_right("read"))] = None,
) -> FileResponse:
    """Пачка, которую собрал этот прогон, — кнопка «Скачать» в строке журнала.

    Не пачка дня: её переписывает каждая следующая сборка, а прогон отдаёт то,
    что собрал сам (`export.archive.keep_run_pack`). Копию с кейсом удалённого
    проекта не отдаём — то же правило, что у пачки (решение владельца 24.09.2026).
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"прогона {run_id} нет")
    kept = (run.params_snapshot or {}).get("pack")
    if not kept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="этот прогон своей пачки не оставил: её оставляют сборки кейсов, "
            "собравшие архив, начиная с 25.09.2026",
        )
    path = await anyio.to_thread.run_sync(run_pack_path, config.export.output_dir, str(kept))
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"файла пачки прогона {run_id} на диске нет",
        )
    if await holds_deleted_case(session, path):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=RUN_PACK_OF_DELETED)
    return FileResponse(path, filename=path.name, media_type="application/zip")


@dataclass(frozen=True, slots=True)
class Cycle:
    """Что строка цикла по файлу знает с рождения: свои проекты и смету."""

    projects: list[int]
    units: int


async def _enqueue(
    session: SessionDep,
    user_id: int,
    *,
    job: Callable[..., object],
    stage: str,
    refresh: bool = False,
    cycle: Cycle | None = None,
) -> RunStarted:
    """Создать прогон под замком постановки и поставить задачу.

    «Нет активных» и строка прогона неделимы: между ними поместился бы второй
    запрос. Тем же замком берёт удаление проекта (`storage.locks`).
    """
    await hold_start(session)
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

    total = (
        len(cycle.projects)
        if cycle is not None
        else int(await session.scalar(select(func.count()).select_from(Project)) or 0)
    )
    key = f"run-{uuid4().hex}"
    run = await open_run(
        session, started_by=user_id, projects_total=total, stage=stage, job_key=key
    )
    if cycle is not None:
        # Смета — для показа «смета → факт»; резерв units держат ступени, не цикл.
        run.units_estimated = cycle.units
        run.params_snapshot = {**(run.params_snapshot or {}), "projects": cycle.projects}
    await session.commit()

    queue = build_queue()
    queued_as = (
        await queue.enqueue(job, run.id, refresh, key=key)
        if refresh
        else await queue.enqueue(job, run.id, key=key)
    )
    logger.info("run_enqueued", extra={"run_id": run.id, "queued_as": queued_as})
    return RunStarted(run_id=run.id, queued_as=queued_as)
