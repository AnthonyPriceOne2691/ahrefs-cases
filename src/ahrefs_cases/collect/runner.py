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
from ahrefs_cases.collect.ahrefs_transport import AhrefsHTTPError, AhrefsUnavailableError
from ahrefs_cases.collect.breaker import ConsecutiveFailureBreaker
from ahrefs_cases.collect.budget import (
    record_cached,
    record_spend,
    reserve,
    reserved_units,
    run_saved,
    run_spend,
)
from ahrefs_cases.collect.factory import build_provider
from ahrefs_cases.collect.plan import CollectTask, build_stage1_plan, build_stage2_plan
from ahrefs_cases.collect.provider import AhrefsProvider, HistoryResult
from ahrefs_cases.collect.quota import FixtureQuota, QuotaSource, preflight
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
from ahrefs_cases.collect.series import store_history
from ahrefs_cases.storage._enums import ProjectStatus, RunItemOutcome
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run

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
    projects_aborted: int
    """Задачи, которых не было: предохранитель остановил прогон. Отдельное
    число, потому что это не «упало», а «не спрашивали» — и повторный прогон
    по ним обязателен."""

    tasks_total: int = 0
    """Задач в прогоне: на шаге 2 их вчетверо больше, чем проектов. Отдельное
    число, потому что «проектов 3, собрано 12» человеку показывать нельзя."""

    points_written: int = 0
    units_spent: int = 0
    units_estimated: int = 0
    """Смета до старта. Хранится рядом с фактом: расхождение между ними —
    единственный способ узнать, что модель стоимости врёт, до Ф7."""

    error: str = ""
    requests_made: int = 0
    requests_saved: int = 0
    """Сколько запросов сделано и сколько не понадобилось. Два числа, а не одно:
    «сделано 0» без «сэкономлено 100» читается как сломанный прогон."""

    def as_lines(self) -> list[str]:
        return [
            f"прогон {self.run_id}: {self.status}",
            f"проектов: {self.projects_total} "
            f"(собрано {self.projects_ok}, пропущено {self.projects_skipped}, "
            f"упало {self.projects_failed}, не выполнено {self.projects_aborted})",
            f"задач: {self.tasks_total}",
            f"точек записано: {self.points_written}",
            f"запросов: сделано {self.requests_made}, сэкономлено кэшем {self.requests_saved}",
            f"units: смета {self.units_estimated}, потрачено {self.units_spent}",
            *([f"причина: {self.error}"] if self.error else []),
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
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
) -> RunReport:
    """Собрать шаг 1 по списку проектов. Провайдер — из конфига, если не задан.

    `now` параметром: от него зависит граница закрытого месяца, и тест не должен
    подкручивать системные часы, чтобы её проверить.
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
            session, engine, run, projects, now=now, refresh=refresh, quota=quota
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
    *,
    now: date | None,
    refresh: bool,
    quota: QuotaSource | None,
    stage: int = 1,
) -> RunReport:
    """Тело прогона. Вынесено, чтобы перехват выше читался одной страницей."""
    build = build_stage1_plan if stage == 1 else build_stage2_plan
    plan = await build(
        session,
        projects,
        source=engine.source,
        now=now or date.today(),  # noqa: DTZ011 — календарная граница месяца
        refresh=refresh,
    )
    estimate = plan.estimated_units()

    state = await preflight(
        quota or FixtureQuota(),
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

    async def one(task: CollectTask) -> _TaskOutcome:
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
                return _TaskOutcome(
                    task=task, outcome=RunItemOutcome.SKIPPED_ABORTED, reason=breaker.reason()
                )
            if asyncio.get_running_loop().time() >= deadline:
                return _TaskOutcome(
                    task=task,
                    outcome=RunItemOutcome.SKIPPED_ABORTED,
                    reason=(
                        f"прогон превысил лимит {config.ahrefs.run_timeout_sec} с и остановлен. "
                        "Запрос по этому домену не делался; собранное сохранено, "
                        "повторный запуск догрузит остаток."
                    ),
                )
            outcome = await _fetch_one(engine, task)
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

    await _mark_projects(session, [])
    await session.commit()
    return points


async def _store_outcome(session: AsyncSession, run: Run, item: _TaskOutcome) -> int:
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
) -> RunReport:
    """Шаг 2 воронки: дорогие метрики только по переданным проектам.

    Список кандидатов приходит **снаружи** — от `funnel.preliminary_candidates`,
    а с Ф3 от классификации. Здесь механизм, а не критерий: правило отбора,
    оказавшись и тут, и там, разошлось бы при первой же правке порогов.
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
        return await _execute_run(
            session,
            engine,
            run,
            projects,
            now=now,
            refresh=refresh,
            quota=quota,
            stage=2,
        )
    except Exception as exc:
        logger.exception("collect_stage2_crashed", extra={"run_id": run.id})
        await _fail_run(session, run, exc)
        raise


async def collect_all(
    session: AsyncSession,
    provider: AhrefsProvider | None = None,
    *,
    now: date | None = None,
    refresh: bool = False,
    quota: QuotaSource | None = None,
) -> RunReport:
    """Прогон по всем проектам в базе — то, что делает CLI."""
    projects = (await session.execute(select(Project))).scalars().all()
    return await collect_projects(
        session, list(projects), provider, now=now, refresh=refresh, quota=quota
    )


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
    except Exception as exc:
        # Неизвестная ошибка (разбор ответа, кодировка, чужая библиотека) не
        # имеет права уронить прогон на сотню доменов. Логируется целиком со
        # стеком: свернуть незнакомое в строку — значит потерять единственный
        # шанс понять, что это было. `BaseException` сюда не попадает, поэтому
        # отмена прогона остаётся отменой, а не «падением по своей вине».
        logger.exception(
            "collect_task_crashed",
            extra={"domain": task.domain, "endpoint": task.spec.name},
        )
        return _TaskOutcome(
            task=task,
            outcome=RunItemOutcome.FAILED,
            reason=f"неожиданная ошибка {type(exc).__name__}: {exc}",
        )

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


_PROJECT_STATUS_BY_OUTCOME = {
    RunItemOutcome.OK: ProjectStatus.COLLECTED,
    RunItemOutcome.SKIPPED_NO_DATA: ProjectStatus.SKIPPED,
    RunItemOutcome.FAILED: ProjectStatus.FAILED,
}
"""`SKIPPED_ABORTED` намеренно отсутствует: по такому домену мы ничего не
спрашивали, и менять его статус значило бы записать незнание как результат."""


async def _apply_project_status(session: AsyncSession, item: _TaskOutcome) -> None:
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


async def _mark_projects(session: AsyncSession, outcomes: Sequence[_TaskOutcome]) -> None:
    """Совместимость: статусы теперь проставляются по мере готовности задач."""
    for item in outcomes:
        await _apply_project_status(session, item)


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
