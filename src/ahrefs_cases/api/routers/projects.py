"""Проекты: список с группами и карточка с объяснением вердикта.

Карточка показывает **записанный** вердикт, а не пересчитанный на лету: экран
обязан отвечать то же, что таблица и PDF (урок L41). Пересчёт — отдельное
действие со своей версией порогов.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import (
    MAX_PAGE,
    ProjectCard,
    ProjectRow,
    ReasonRow,
    SeriesRow,
    VerdictView,
)
from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.classify.series import load_series
from ahrefs_cases.storage import Group, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
    dependencies=[Depends(require_right("read"))],
)


@router.get("", response_model=list[ProjectRow])
async def list_projects(
    session: SessionDep,
    group: Group | None = None,
    query: Annotated[str | None, Query(max_length=253)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProjectRow]:
    """Список проектов с группой по действующей версии порогов.

    Граница выдачи обязательна и не обходится параметром: `limit` ограничен
    сверху схемой, а не доверием к вызывающему.
    """
    ruleset = await active_ruleset(session)
    stmt = (
        select(Project, Verdict)
        .outerjoin(
            Verdict,
            (Verdict.project_id == Project.id) & (Verdict.ruleset_id == ruleset.id),
        )
        .order_by(Project.domain)
        .limit(limit)
        .offset(offset)
    )
    if group is not None:
        stmt = stmt.where(Verdict.group == group)
    if query:
        stmt = stmt.where(Project.domain.ilike(f"%{query}%"))

    rows = (await session.execute(stmt)).all()
    return [_row(project, verdict) for project, verdict in rows]


@router.get("/{project_id}", response_model=ProjectCard)
async def project_card(
    project_id: int,
    session: SessionDep,
    source: MetricSource = MetricSource.FIXTURE,
) -> ProjectCard:
    """Карточка: поля проекта, вердикт с объяснением и ряды под графики."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет"
        )

    ruleset = await active_ruleset(session)
    verdict = (
        (
            await session.execute(
                select(Verdict).where(
                    Verdict.project_id == project.id, Verdict.ruleset_id == ruleset.id
                )
            )
        )
        .scalars()
        .first()
    )

    series = await load_series(session, project.id, source)
    return ProjectCard(
        project=_row(project, verdict),
        verdict=_verdict_view(verdict, ruleset) if verdict is not None else None,
        series=[
            SeriesRow(metric=metric.value, points=sorted(points.items()))
            for metric, points in sorted(series.items(), key=lambda item: item[0].value)
        ],
    )


def _row(project: Project, verdict: Verdict | None) -> ProjectRow:
    return ProjectRow(
        id=project.id,
        domain=project.domain,
        niche=project.niche,
        geo=project.geo,
        service_type=project.service_type,
        period_start=project.period_start,
        period_end=project.period_end,
        publishable=project.publishable,
        status=project.status.value,
        group=verdict.group.value if verdict is not None else None,
        score=verdict.score if verdict is not None else None,
    )


def _verdict_view(verdict: Verdict, ruleset: Ruleset) -> VerdictView:
    # `reasons` — JSONB: типизирован как `dict[str, object]`, и разбирать его
    # надо явно. Молчаливое `list(...)` на `object` — ровно то место, где
    # чужая форма притворяется нашей (урок L23).
    raw = verdict.reasons.get("checks", [])
    checks: list[dict[str, Any]] = list(raw) if isinstance(raw, list) else []
    return VerdictView(
        group=verdict.group.value,
        score=verdict.score,
        ruleset_version=ruleset.version,
        decided_at=verdict.decided_at,
        reasons=[ReasonRow(**check) for check in checks],
        point_a=_point(verdict.point_a),
        point_b=_point(verdict.point_b),
    )


def _point(payload: dict[str, Any]) -> dict[str, float]:
    """Точка вердикта плоским словарём: значения метрик и производные вместе."""
    values = {str(key): float(value) for key, value in payload.get("values", {}).items()}
    derived = {str(key): float(value) for key, value in payload.get("derived", {}).items()}
    return values | derived
