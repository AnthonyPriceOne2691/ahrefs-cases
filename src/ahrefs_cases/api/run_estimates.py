"""Сметы прогонов: сколько будет стоить и пускает ли квота — одним местом.

Вынесено из `api/routers/runs.py`, когда тот перерос планку длины. Три сметы —
шаг 1, вторая кнопка (B6) и цикл по файлу — сверяются с квотой одной функцией
(`estimate_view`): вторая копия разошлась бы в деньгах.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.schemas import RunEstimate
from ahrefs_cases.classify.candidates import stage2_candidates
from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.collect.budget import reserved_units, uncounted_spend
from ahrefs_cases.collect.factory import build_provider, build_quota
from ahrefs_cases.collect.plan import build_case_plan, build_stage1_plan, build_stage2_plan
from ahrefs_cases.collect.quota import preflight
from ahrefs_cases.storage.models.project import Project


async def cycle_estimate(session: AsyncSession, only: Sequence[int]) -> RunEstimate:
    """Смета цикла по проектам файла: шаг 1, шаг 2 и данные под кейс по верхней границе.

    Кандидаты шага 2 выясняются только шагом 1, поэтому границу дают нынешние
    кандидаты и проекты, за которых шаг 1 заплатит впервые: группа новых до
    шага 1 неизвестна, и считать их «не кандидатами» значило бы занизить цену
    цикла, который потом упрётся в квоту посередине. Одна смета на обе
    ступени, потому что и подтверждение одно.
    """
    windows = await point_windows(session)
    source = build_provider().source
    today = date.today()  # noqa: DTZ011 — календарная граница закрытого месяца
    stmt = select(Project).where(Project.id.in_(list(only)))
    projects = list((await session.execute(stmt)).scalars().all())
    first = await build_stage1_plan(session, projects, source=source, now=today, windows=windows)
    unknown = {task.project_id for task in first.tasks}
    wanted = set(await stage2_candidates(session, projects, source=source)) | unknown
    chosen = [project for project in projects if project.id in wanted]
    second = await build_stage2_plan(session, chosen, source=source, now=today, windows=windows)
    case = await build_case_plan(session, chosen, source=source, now=today, windows=windows)
    lines = [
        *first.scheme_breakdown().as_lines(),
        *second.scheme_breakdown().as_lines(),
        *case.scheme_breakdown().as_lines(),
    ]
    if chosen:
        lines.append(
            "шаг 2 и данные под кейс посчитаны по нынешним кандидатам и новым проектам — "
            "это верхняя граница: докупаются только тем, кто после шага 1 окажется кандидатом"
        )
    return await estimate_view(
        session,
        projects=len(projects),
        units=first.estimated_units() + second.estimated_units() + case.estimated_units(),
        planned=len(first.tasks) + len(second.tasks) + len(case.tasks),
        cached=len(first.cached) + len(second.cached) + len(case.cached),
        lines=lines,
    )


async def estimate_view(
    session: AsyncSession,
    *,
    projects: int,
    units: int,
    planned: int,
    cached: int,
    lines: list[str],
) -> RunEstimate:
    """Смета против квоты — одна на обе кнопки: вторая копия разошлась бы в деньгах.

    Считать не по кому — строк схемы нет: пустой план печатает «данные по
    этому списку уже куплены», а это неправда про список, где собирать не по
    кому. Пустоту объясняет окно своими словами.
    """
    reserved = await reserved_units(session)
    state = await preflight(
        build_quota(),
        needed=units,
        reserved=reserved,
        uncounted=await uncounted_spend(session),
    )
    return RunEstimate(
        projects=projects,
        units_estimated=units,
        requests_planned=planned,
        requests_cached=cached,
        scheme_lines=lines if projects else [],
        quota_left=state.left,
        quota_reserved=reserved,
        verdict=state.verdict.value,
        may_start=state.may_start,
        reason=state.reason,
    )
