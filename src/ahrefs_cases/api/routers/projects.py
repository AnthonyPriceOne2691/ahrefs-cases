"""Проекты: список с группами, карточка с объяснением вердикта и удаление.

Карточка показывает **записанный** вердикт, а не пересчитанный на лету: экран
обязан отвечать то же, что таблица и PDF (урок L41). Пересчёт — отдельное
действие со своей версией порогов.

Удаление — жёсткое, каскадом, под правом `delete_projects` (владелец, 24.09.2026).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import (
    MAX_PAGE,
    ChartBlock,
    ComparisonRow,
    ProjectCard,
    ProjectDeletion,
    ProjectRow,
    ReasonRow,
    SeriesRow,
    VerdictView,
)
from ahrefs_cases.cases.builder import chart_series
from ahrefs_cases.cases.model import CASE_SUBJECTS, SUBJECT_LABELS
from ahrefs_cases.classify.deltas import delta_of
from ahrefs_cases.classify.points import window_from
from ahrefs_cases.classify.rules import SUPPORTING_METRICS
from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.classify.series import load_series
from ahrefs_cases.classify.verdicts import source_mismatch
from ahrefs_cases.collect.factory import build_provider
from ahrefs_cases.collect.purchases import bought_metrics
from ahrefs_cases.export import removal
from ahrefs_cases.export.archive import newest_pack
from ahrefs_cases.export.charts import curve_blocks
from ahrefs_cases.export.grouping import Grouping
from ahrefs_cases.export.html_renderer import POINTS_NOTE
from ahrefs_cases.storage import Group, Metric, MetricSource, RunStatus
from ahrefs_cases.storage.locks import hold_start, work_is_idle
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.verdict import Verdict

logger = logging.getLogger(__name__)
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


async def _active_verdict(session: SessionDep, project_id: int) -> Verdict | None:
    """Вердикт проекта по действующей версии порогов — один запрос на двоих.

    Карточка и графики спрашивают одно и то же: вердикты разных версий живут
    рядом, и «какой из них действующий» обязано решаться в одном месте.
    """
    ruleset = await active_ruleset(session)
    stmt = select(Verdict).where(Verdict.project_id == project_id, Verdict.ruleset_id == ruleset.id)
    return (await session.execute(stmt)).scalars().first()


def configured_source() -> MetricSource:
    """Каким источником помечены точки текущего режима.

    Спрашивается у фабрики провайдера, а **не** подставляется умолчанием
    обработчика. Умолчание `MetricSource.FIXTURE` в сигнатуре означало ровно
    одно: в живом режиме карточка читала бы фикстурные ряды и показывала пустые
    графики при целой базе. Это буквальное повторение L53 — выбор режима
    принадлежит конфигу, а был сделан вызывающим.
    """
    return build_provider().source


@router.get("/{project_id}", response_model=ProjectCard)
async def project_card(
    project_id: int,
    session: SessionDep,
    source: Annotated[MetricSource | None, Query()] = None,
) -> ProjectCard:
    """Карточка: поля проекта, вердикт с объяснением и ряды под графики."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет"
        )

    ruleset = await active_ruleset(session)
    verdict = await _active_verdict(session, project.id)

    shown = source or configured_source()
    series = await load_series(session, project.id, shown)
    return ProjectCard(
        project=_row(project, verdict),
        verdict=(
            _verdict_view(verdict, ruleset, await bought_metrics(session, project.domain))
            if verdict is not None
            else None
        ),
        series=[
            SeriesRow(metric=metric.value, points=sorted(points.items()))
            for metric, points in sorted(series.items(), key=lambda item: item[0].value)
        ],
        series_source=shown.value,
        # Карточка кладёт числа вердикта рядом с кривыми рядов — ровно та пара,
        # которая разъехалась в кейсе (Z10). Правило расхождения берётся у
        # вердикта, а не пишется здесь второй раз.
        source_mismatch=(source_mismatch(verdict.source, shown) if verdict is not None else None),
    )


@router.get(
    "/{project_id}/charts",
    response_model=list[ChartBlock],  # unbounded-ok: графиков ровно два, набор задан CHART_BLOCKS
)
async def project_charts(
    project_id: int,
    session: SessionDep,
    source: Annotated[MetricSource | None, Query()] = None,
    grouping: Annotated[Grouping, Query()] = Grouping.MONTH,
) -> list[ChartBlock]:
    """Графики проекта — **тот же рисунок**, что уходит в PDF.

    Компоновка общая (`export.charts.curve_blocks`), поэтому веб-карточка и
    кейс показывают одни кривые. Собирать их на фронте по рядам было бы вторым
    рисунком: он разошёлся бы с первым на шкале, сглаживании или подписях, и
    сотрудник с клиентом увидели бы разные графики одного проекта.

    `grouping` сворачивает кривую в кварталы или годы. Свёртка бесплатна
    (месяцы уже собраны) и делается здесь, а не на фронте: правило зависит от
    природы метрики — поток складывается, запас берётся на конец периода.
    Точки А и Б при этом не пересчитываются: они принадлежат вердикту и его
    окнам, а не виду экрана.

    Полосы окон А и Б берутся из **записанного** вердикта (L41): карточка
    обязана объяснять то число, которое стоит в таблице и в кейсе. Вердикта
    нет — графики рисуются без полос, а не пропадают: «плохому» проекту кейс
    не собирают, но смотреть на его кривые всё равно нужно.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет"
        )

    verdict = await _active_verdict(session, project.id)
    series = await load_series(session, project.id, source or configured_source())
    blocks = curve_blocks(
        chart_series(series),
        period_start=project.period_start,
        window_a=_window(verdict.point_a if verdict else None, forward=True),
        window_b=_window(verdict.point_b if verdict else None, forward=False),
        # Полосы окон подписываются теми же числами, что стоят в таблице А → Б:
        # рисунок и таблица на одном экране обязаны говорить одно (Z32).
        point_a=_point(verdict.point_a) if verdict else None,
        point_b=_point(verdict.point_b) if verdict else None,
        # Шаг кривой — перечисление: опечатка в параметре отвечает `422`, а не
        # молча показывает месяцы человеку, выбравшему кварталы.
        grouping=grouping,
    )
    return [ChartBlock(**block) for block in blocks]


DeleteDep = Annotated[object, Depends(require_right("delete_projects"))]


@router.get("/{project_id}/deletion", response_model=ProjectDeletion)
async def deletion_preview(
    project_id: int, session: SessionDep, _: DeleteDep = None
) -> ProjectDeletion:
    """Что уйдёт вместе с проектом — ничего не удаляя; та же форма, что у удаления."""
    _, view = await _deletion(session, await _project_or_404(session, project_id))
    return view


@router.delete("/{project_id}", response_model=ProjectDeletion)
async def delete_project(
    project_id: int, session: SessionDep, _: DeleteDep = None
) -> ProjectDeletion:
    """Удалить проект со всем, что ему принадлежит: замки → проверки → удаление →
    коммит → файлы. Замок постановки не пустит новый прогон между проверкой и
    удалением; идущей работе удаление отказывает — посреди неё оно роняло прогон
    на внешнем ключе раньше записи расхода (урок L202)."""
    await hold_start(session)
    project = await _project_or_404(session, project_id)
    await _refuse_while_working(session)
    trace, view = await _deletion(session, project)
    await removal.delete_rows(session, project)
    await session.commit()
    files = await removal.own_files(session, project.id, trace, config.export.output_dir)
    removed = await anyio.to_thread.run_sync(removal.remove_files, files)
    logger.info("project_deleted", extra={**view.model_dump(), "files": removed})
    return view.model_copy(update={"files": removed})


async def _project_or_404(session: SessionDep, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет"
        )
    return project


async def _refuse_while_working(session: SessionDep) -> None:
    """Отказ, пока кто-то пишет строки проектов, — с тем, чего ждать."""
    busy = select(Run).where(Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING])).limit(1)
    active = (await session.execute(busy)).scalars().first()
    if active is not None:
        detail = (
            f"прогон {active.id} ещё идёт ({active.status.value}): он пишет строки проектов "
            "— удалите проект, когда прогон закончится"
        )
    elif not await work_is_idle(session):
        detail = (
            "сервис дописывает результаты по проектам — хвост прогона или пересчёт порогов: "
            "удалите проект через минуту"
        )
    else:
        return
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _deletion(
    session: SessionDep, project: Project
) -> tuple[removal.ProjectTrace, ProjectDeletion]:
    trace = await removal.trace_of(session, project)
    files = await removal.own_files(session, project.id, trace, config.export.output_dir)
    pack = await anyio.to_thread.run_sync(newest_pack, config.export.output_dir)
    blocked = pack is not None and await removal.holds_deleted_case(
        session, pack, without=project.id
    )
    return trace, ProjectDeletion(
        project_id=project.id,
        domain=project.domain,
        metric_points=trace.metric_points,
        verdicts=trace.verdicts,
        cases=trace.cases,
        files=len(files),
        run_items=trace.run_items,
        twin_campaigns=trace.twin_campaigns,
        pack_blocked=blocked,
    )


def _window(payload: dict[str, Any] | None, *, forward: bool) -> list[date]:
    """Месяцы окна точки из записанного вердикта. Нет вердикта — нет полосы."""
    if not payload:
        return []
    try:
        anchor = date.fromisoformat(str(payload["at"]))
        months = int(payload["months_used"])
    except (KeyError, TypeError, ValueError):
        # Форма не та — рисуем без полос. Ронять карточку из-за оформления
        # значило бы прятать и вердикт, и кривые, которые в порядке.
        logger.warning("вердикт без пригодной точки: полосы окна не нарисованы")
        return []
    return window_from(anchor, months, forward=forward)


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


def _verdict_view(
    verdict: Verdict, ruleset: Ruleset, bought: frozenset[Metric] | None = None
) -> VerdictView:
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
        reasons=[_reason(check, bought) for check in checks],
        points_note=POINTS_NOTE,
        source=verdict.source.value if verdict.source is not None else None,
        point_a=_point(verdict.point_a),
        point_b=_point(verdict.point_b),
        comparison=_comparison(verdict),
    )


def _reason(check: dict[str, Any], bought: frozenset[Metric] | None) -> ReasonRow:
    """Условие вердикта, а к пустому факту — причина пустоты (Z25).

    Причину знает журнал расхода, а не форма записи: прочерк одинаков и когда
    историю метрики не покупали (шаг 2 платится только кандидатам в кейсы), и
    когда купили, а Ahrefs ничего не отдал. Журнал молчит про домен — молчим и
    мы: догадка здесь дороже прочерка.
    """
    row = ReasonRow(**check)
    if row.fact is not None or bought is None:
        return row
    metric = SUPPORTING_METRICS.get(row.subject.rsplit(".", 1)[-1])
    if metric is None:
        return row
    return row.model_copy(update={"fact_missing": "no_data" if metric in bought else "not_bought"})


def _comparison(verdict: Verdict) -> list[ComparisonRow]:
    """Таблица «А → Б» — та же, что в кейсе, и собранная из того же.

    Подписи берутся из словаря кейса, рост — из арифметики классификации. Ни то,
    ни другое не повторяется на фронте: две копии разошлись бы, и экран с PDF
    начали бы называть метрики по-разному (урок L75).

    Порядок — `CASE_SUBJECTS`: он выбран для клиентского листа, и держать на
    экране другой значило бы заставлять человека искать строку заново.
    """
    before, after = _point(verdict.point_a), _point(verdict.point_b)
    rows: list[ComparisonRow] = []
    for subject in CASE_SUBJECTS:
        if subject not in before or subject not in after:
            # Метрику не покупали или купили только к одной точке: показать
            # половину сравнения значило бы предложить сравнить с пустотой.
            continue
        change = delta_of(before[subject], after[subject])
        rows.append(
            ComparisonRow(
                subject=subject,
                label=SUBJECT_LABELS[subject],
                before=change.before,
                after=change.after,
                absolute=change.absolute,
                pct=change.pct,
            )
        )
    return rows


def _point(payload: dict[str, Any]) -> dict[str, float]:
    """Точка вердикта плоским словарём: значения метрик и производные вместе."""
    values = {str(key): float(value) for key, value in payload.get("values", {}).items()}
    derived = {str(key): float(value) for key, value in payload.get("derived", {}).items()}
    return values | derived
