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
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.breaker import ConsecutiveFailureBreaker
from ahrefs_cases.collect.budget import (
    record_cached,
    record_spend,
    reserve,
    reserved_units,
    run_saved,
    run_spend,
)
from ahrefs_cases.collect.factory import build_provider, build_quota
from ahrefs_cases.collect.fetch import TaskOutcome, fetch_one
from ahrefs_cases.collect.plan import (
    CollectTask,
    build_case_plan,
    build_stage1_plan,
    build_stage2_plan,
)
from ahrefs_cases.collect.provider import AhrefsProvider
from ahrefs_cases.collect.quota import QuotaSource, preflight
from ahrefs_cases.collect.run_journal import (
    add_item,
    count_outcome,
    finish_run,
    open_run,
    reject_run,
    start_run,
    system_user,
)
from ahrefs_cases.collect.run_reaper import reap_stale_runs
from ahrefs_cases.collect.run_report import RunReport
from ahrefs_cases.collect.scheme import PointWindows
from ahrefs_cases.collect.series import store_history
from ahrefs_cases.storage._enums import ProjectStatus, RunItemOutcome
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Параметры прогона: что уточняет вызывающий, а не конфиг.

    Одним объектом, а не пятью аргументами: у `_execute_run` их стало девять, и
    гейт сложности остановил поставку — справедливо. Девять позиций в сигнатуре
    читаются только по имени, и первая же перепутанная пара (`refresh`/`stage`)
    была бы тихой: типы у них разные, а вот `now`/`windows` уже нет.

    `now` параметром, потому что от него зависит граница закрытого месяца, и
    тест не должен подкручивать системные часы. `windows` — окна точек из
    активной версии порогов: контракт `layers` запрещает `collect` знать про
    `classify`, поэтому их передаёт тот, кто читает пороги.
    """

    now: date | None = None
    refresh: bool = False
    quota: QuotaSource | None = None
    windows: PointWindows | None = None
    stage: int = 1


_PLAN_BUILDERS = {1: build_stage1_plan, 2: build_stage2_plan, 3: build_case_plan}
"""Ступень прогона → построитель плана.

Таблицей, а не лестницей `if`: ступеней стало три, и четвёртая (если появится)
не должна требовать правки тела прогона."""


async def collect_projects(
    session: AsyncSession,
    projects: Sequence[Project],
    provider: AhrefsProvider | None = None,
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
    windows: PointWindows | None = None,
) -> RunReport:
    """Собрать шаг 1 по списку проектов. Провайдер — из конфига, если не задан.

    `now` параметром: от него зависит граница закрытого месяца, и тест не должен
    подкручивать системные часы, чтобы её проверить.

    `windows` — окна точек из активной версии порогов. Приходят сверху, потому
    что контракт `layers` запрещает `collect` знать про `classify`; кто читает
    пороги, тот и передаёт (`scripts/run_collect.py`). Без них покупается
    бесплатный максимум под минимальную стоимость запроса.
    """
    engine = provider or build_provider()
    # До открытия своего прогона подметаем чужие зависшие: их резервы units
    # иначе занимают квоту вечно (паттерн CRM, см. `run_reaper`). Место
    # временное — с появлением сметы в этой же поставке вызов переедет в
    # preflight, туда, где результат нужен.
    await reap_stale_runs(session)
    user = await system_user(session)
    run = await open_run(session, started_by=user.id, projects_total=len(projects))
    # Коммит сразу: до него строки прогона не существует ни для другого
    # процесса (а его резерв обязан быть виден чужой смете), ни для реапера.
    await session.commit()

    try:
        return await _execute_run(
            session,
            engine,
            run,
            projects,
            RunOptions(now=now, refresh=refresh, quota=quota, windows=windows),
        )
    except Exception as exc:
        # Широко и с логом: любая ошибка вне задач (база, запись, финализация)
        # обязана закрыть прогон статусом, иначе строка навсегда останется в
        # `running` и её резерв — в чужой смете. Исключение после этого летит
        # дальше: проглотить его значило бы соврать вызывающему успехом.
        logger.exception("collect_run_crashed", extra={"run_id": run.id})
        await _fail_run(session, run, exc)
        raise


async def _execute_run(
    session: AsyncSession,
    engine: AhrefsProvider,
    run: Run,
    projects: Sequence[Project],
    options: RunOptions,
) -> RunReport:
    """Тело прогона. Вынесено, чтобы перехват выше читался одной страницей."""
    build = _PLAN_BUILDERS[options.stage]
    plan = await build(
        session,
        projects,
        source=engine.source,
        now=options.now or date.today(),  # noqa: DTZ011 — календарная граница месяца
        refresh=options.refresh,
        windows=options.windows,
    )
    estimate = plan.estimated_units()
    scheme = plan.scheme_breakdown()

    state = await preflight(
        options.quota or build_quota(),
        needed=estimate,
        reserved=await reserved_units(session),
    )
    if not state.may_start:
        # Отказ до первого запроса — единственное место, где он что-то стоит.
        # Проверка по ходу нашла бы нехватку, когда часть units уже потрачена.
        await reject_run(session, run, state.reason)
        await session.commit()
        logger.warning("collect_run_rejected", extra={"run_id": run.id, "reason": state.reason})
        return RunReport(
            run_id=run.id,
            status=run.status.value,
            projects_total=run.projects_total,
            projects_ok=0,
            projects_skipped=0,
            projects_failed=0,
            projects_aborted=0,
            points_written=0,
            units_spent=0,
            units_estimated=estimate,
            error=state.reason,
        )

    await reserve(session, run.id, estimate)
    await start_run(session, run)
    await session.commit()

    for skipped in plan.cached:
        await record_cached(session, run.id, skipped.spec.name, skipped.domain)
        await add_item(
            session,
            run,
            project_id=skipped.project_id,
            raw_domain=skipped.domain,
            outcome=RunItemOutcome.OK,
            reason=skipped.reason,
        )
    await session.commit()

    points = await _execute_tasks(session, engine, run, plan.tasks)
    await finish_run(session, run)
    await session.commit()

    return RunReport(
        run_id=run.id,
        status=run.status.value,
        projects_total=run.projects_total,
        projects_ok=run.projects_ok,
        projects_skipped=await count_outcome(session, run.id, RunItemOutcome.SKIPPED_NO_DATA),
        projects_aborted=await count_outcome(session, run.id, RunItemOutcome.SKIPPED_ABORTED),
        tasks_total=len(plan.tasks) + len(plan.cached),
        scheme_lines=tuple(scheme.as_lines()),
        cost_per_100=scheme.per_100_urls(run.projects_total),
        projects_failed=run.projects_failed,
        points_written=points,
        units_spent=await run_spend(session, run.id),
        units_estimated=estimate,
        requests_made=len(plan.tasks),
        requests_saved=await run_saved(session, run.id),
    )


async def _execute_tasks(
    session: AsyncSession,
    engine: AhrefsProvider,
    run: Run,
    tasks: Sequence[CollectTask],
) -> int:
    """Выполнить задачи, записывая результат **по мере готовности**.

    Ф2а писала всё после `gather`: прогон, убитый на семидесятом домене, терял
    данные шестидесяти девяти, за которые units уже списаны. Здесь каждая
    завершённая задача попадает в базу сразу, а каждые
    `COLLECT_CHECKPOINT_EVERY` задач фиксируются коммитом.

    Возобновления как отдельного механизма не нужно: следующий прогон увидит
    собранное через кэш и докупит только остаток.
    """
    semaphore = asyncio.Semaphore(config.ahrefs.max_parallel)
    breaker = ConsecutiveFailureBreaker(limit=config.ahrefs.breaker_max_failures)
    deadline = asyncio.get_running_loop().time() + config.ahrefs.run_timeout_sec
    """Прогон обязан закончиться до дедлайна.

    Не для красоты: реапер судит о смерти прогона по возрасту, и это верно
    только пока живой прогон физически не может идти дольше своего лимита. В
    CRM гарантию давал таймаут RQ-джобы, у нас до Ф5 очереди нет — значит
    лимит держит сам прогон (Z1 в docs/FINDINGS.md).
    """

    async def one(task: CollectTask) -> TaskOutcome:
        """Одна задача под семафором.

        Предохранитель проверяется и обновляется **внутри** семафора, а не в
        цикле потребления результатов. Снаружи это не работает: `as_completed`
        стартует все корутины сразу, проверка успевает пройти до первой
        неудачи, и предохранитель не срабатывает вообще — поймано тестом C14,
        который до этой правки видел 10 запросов вместо 3.

        Перелёт на величину `max_parallel` остаётся: задачи, уже ушедшие в
        сеть, не отзываются. Это цена параллельности, а не дефект.
        """
        async with semaphore:
            if breaker.tripped:
                return TaskOutcome(
                    task=task, outcome=RunItemOutcome.SKIPPED_ABORTED, reason=breaker.reason()
                )
            if asyncio.get_running_loop().time() >= deadline:
                return TaskOutcome(
                    task=task,
                    outcome=RunItemOutcome.SKIPPED_ABORTED,
                    reason=(
                        f"прогон превысил лимит {config.ahrefs.run_timeout_sec} с и остановлен. "
                        "Запрос по этому домену не делался; собранное сохранено, "
                        "повторный запуск догрузит остаток."
                    ),
                )
            outcome = await fetch_one(engine, task)
            breaker.record(ok=outcome.outcome is not RunItemOutcome.FAILED)
            return outcome

    points = 0
    for done, future in enumerate(asyncio.as_completed([one(task) for task in tasks]), start=1):
        item = await future
        points += await _store_outcome(session, run, item)
        if done % config.ahrefs.checkpoint_every == 0:
            # Чекпойнт: прогон, убитый после этой точки, теряет не больше
            # `checkpoint_every` доменов — за них уже заплачено.
            await session.commit()

    await session.commit()
    return points


async def _store_outcome(session: AsyncSession, run: Run, item: TaskOutcome) -> int:
    """Записать исход одной задачи: точки, расход, строку журнала, статус проекта."""
    points = 0
    if item.result is not None:
        points = await store_history(session, item.task.project_id, item.result)
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
    await _apply_project_status(session, item)
    return points


async def collect_stage2(
    session: AsyncSession,
    project_ids: Sequence[int],
    provider: AhrefsProvider | None = None,
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
    windows: PointWindows | None = None,
) -> RunReport:
    """Шаг 2 воронки: дорогие метрики только по переданным проектам.

    Список кандидатов приходит **снаружи** — от `funnel.preliminary_candidates`,
    а с Ф3 от классификации. Здесь механизм, а не критерий: правило отбора,
    оказавшись и тут, и там, разошлось бы при первой же правке порогов.
    """
    return await _run_by_ids(
        session,
        project_ids,
        provider,
        RunOptions(now=now, refresh=refresh, quota=quota, windows=windows, stage=2),
    )


async def collect_case_data(
    session: AsyncSession,
    project_ids: Sequence[int],
    provider: AhrefsProvider | None = None,
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
    windows: PointWindows | None = None,
) -> RunReport:
    """Ступень кейса: докупить кривую позиций, стоимость трафика и DR.

    Только тем, у кого кейс будет: список приходит снаружи — проекты с вердиктом
    `good` или `medium`. Сбор не читает вердикты сам, потому что контракт слоёв
    запрещает `collect` знать про `classify`.
    """
    return await _run_by_ids(
        session,
        project_ids,
        provider,
        RunOptions(now=now, refresh=refresh, quota=quota, windows=windows, stage=3),
    )


async def _run_by_ids(
    session: AsyncSession,
    project_ids: Sequence[int],
    provider: AhrefsProvider | None,
    options: RunOptions,
) -> RunReport:
    """Прогон по списку id: открыть, выполнить, не потерять статус при ошибке.

    Общее тело шага 2 и ступени кейса. Порознь они отличались только номером
    ступени, и гейт копипаста поймал это на второй же ступени — справедливо:
    две копии открытия прогона разошлись бы при первой правке реапера.
    """
    engine = provider or build_provider()
    await reap_stale_runs(session)
    user = await system_user(session)
    projects = list(
        (await session.execute(select(Project).where(Project.id.in_(list(project_ids)))))
        .scalars()
        .all()
    )
    run = await open_run(session, started_by=user.id, projects_total=len(projects))
    await session.commit()

    try:
        return await _execute_run(session, engine, run, projects, options)
    except Exception as exc:
        logger.exception("collect_run_crashed", extra={"run_id": run.id, "stage": options.stage})
        await _fail_run(session, run, exc)
        raise


async def collect_all(
    session: AsyncSession,
    provider: AhrefsProvider | None = None,
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
    windows: PointWindows | None = None,
) -> RunReport:
    """Прогон по всем проектам в базе — то, что делает CLI."""
    projects = (await session.execute(select(Project))).scalars().all()
    return await collect_projects(
        session, list(projects), provider, now=now, refresh=refresh, quota=quota, windows=windows
    )


_PROJECT_STATUS_BY_OUTCOME = {
    RunItemOutcome.OK: ProjectStatus.COLLECTED,
    RunItemOutcome.SKIPPED_NO_DATA: ProjectStatus.SKIPPED,
    RunItemOutcome.FAILED: ProjectStatus.FAILED,
}
"""`SKIPPED_ABORTED` намеренно отсутствует: по такому домену мы ничего не
спрашивали, и менять его статус значило бы записать незнание как результат."""


async def _apply_project_status(session: AsyncSession, item: TaskOutcome) -> None:
    """Статус проекта по исходу сбора.

    Статус двигает прогон, а не приём списка (см. `intake/upsert.py`): иначе
    повторная загрузка файла обнуляла бы результат последнего сбора.
    """
    status = _PROJECT_STATUS_BY_OUTCOME.get(item.outcome)
    if status is None:
        return
    project = await session.get(Project, item.task.project_id)
    if project is not None:
        project.status = status


async def _fail_run(session: AsyncSession, run: Run, exc: Exception) -> None:
    """Закрыть прогон как упавший, не потеряв причину.

    Откат обязателен: сессия после ошибки в транзакции не примет ни одной
    записи, и попытка сохранить статус упала бы второй ошибкой, затерев первую.
    Уже собранное при этом не теряется — оно зафиксировано чекпойнтами.
    """
    try:
        await session.rollback()
        await finish_run(session, run, error=f"{type(exc).__name__}: {exc}")
        await session.commit()
    except SQLAlchemyError:
        # База недоступна совсем: статус сохранить нечем. Прогон останется в
        # `running` и его подметёт реапер — ради этого случая он и написан.
        logger.exception("collect_run_status_not_saved", extra={"run_id": run.id})
