"""Классификация проекта: чтение серий, расчёт, запись вердикта.

Тонкий слой вокруг чистых функций. Сам ничего не решает: его дело — принести
данные, вызвать правила и сохранить результат вместе с версией порогов.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify import points as points_module
from ahrefs_cases.classify import series as series_module
from ahrefs_cases.classify.deltas import between
from ahrefs_cases.classify.rules import Decision, decide
from ahrefs_cases.classify.rulesets import active_ruleset, thresholds_of
from ahrefs_cases.storage._enums import Group, Metric, MetricSource, ProjectStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict


@dataclass(frozen=True, slots=True)
class ClassifyReport:
    """Итог прогона классификации в числах для человека."""

    ruleset_version: str
    total: int
    by_group: dict[Group, int]

    def as_lines(self) -> list[str]:
        order = (Group.GOOD, Group.MEDIUM, Group.POOR, Group.INSUFFICIENT_DATA)
        counts = ", ".join(f"{group.value}: {self.by_group.get(group, 0)}" for group in order)
        return [
            f"пороги версии {self.ruleset_version}",
            f"проектов классифицировано: {self.total}",
            counts,
        ]


@dataclass(frozen=True, slots=True)
class Computed:
    """Посчитанный вердикт до записи: решение, точки и месяцы, по которым считали.

    Существует, чтобы расчёт можно было выполнить, **ничего не записав**:
    пересчёт по версии порогов (Ф3б) и предпросмотр «кто сменит группу» обязаны
    быть одним кодом. Два похожих расчёта разойдутся ровно тогда, когда
    заказчик доверится предпросмотру на калибровке.

    `months` отдаётся наружу, потому что по нему проверяют покрытие: хватило ли
    купленных месяцев под окна этой версии порогов (`classify/coverage.py`).
    """

    decision: Decision
    point_a: points_module.Point
    point_b: points_module.Point
    months: tuple[date, ...]


async def compute_verdict(
    session: AsyncSession,
    project: Project,
    ruleset: Ruleset,
    *,
    source: MetricSource = MetricSource.FIXTURE,
) -> Computed:
    """Посчитать вердикт и **не** записывать. Ahrefs не трогается.

    Чтение серии здесь есть, записи нет: это единственная асимметрия, которую
    предпросмотр себе позволяет — прочитать, чтобы показать.
    """
    thresholds = thresholds_of(ruleset)
    series = await series_module.load_series(session, project.id, source)

    point_a = points_module.point_a(series, project.period_start, thresholds.windows)
    point_b = points_module.point_b(series, project.period_end, thresholds.windows)
    months = series_module.months_covered(series, Metric.ORG_TRAFFIC)
    after_start = [month for month in months if month >= project.period_start]

    decision = decide(
        between(point_a, point_b),
        point_b,
        months_after_start=len(after_start),
        max_gap_months=series_module.max_gap_months(months),
        thresholds=thresholds,
        history_starts_at=months[0] if months else None,
        period_start=project.period_start,
    )
    return Computed(decision=decision, point_a=point_a, point_b=point_b, months=tuple(months))


async def classify_project(
    session: AsyncSession,
    project: Project,
    ruleset: Ruleset,
    *,
    source: MetricSource = MetricSource.FIXTURE,
) -> Decision:
    """Вердикт одного проекта — посчитать и записать."""
    computed = await compute_verdict(session, project, ruleset, source=source)
    await store(session, project, ruleset, computed)
    return computed.decision


async def classify_projects(
    session: AsyncSession,
    projects: Sequence[Project],
    *,
    source: MetricSource = MetricSource.FIXTURE,
) -> ClassifyReport:
    """Классифицировать список проектов по действующей версии порогов."""
    ruleset = await active_ruleset(session)
    by_group: dict[Group, int] = {}
    for project in projects:
        decision = await classify_project(session, project, ruleset, source=source)
        by_group[decision.group] = by_group.get(decision.group, 0) + 1
    await session.flush()
    return ClassifyReport(ruleset_version=ruleset.version, total=len(projects), by_group=by_group)


async def classify_all(
    session: AsyncSession, *, source: MetricSource = MetricSource.FIXTURE
) -> ClassifyReport:
    projects = list((await session.execute(select(Project))).scalars().all())
    return await classify_projects(session, projects, source=source)


async def store(
    session: AsyncSession,
    project: Project,
    ruleset: Ruleset,
    computed: Computed,
) -> None:
    """Записать посчитанный вердикт. Повтор по той же версии обновляет его.

    Ключ `(project_id, ruleset_id)` — из модели Ф1: один проект на одной версии
    порогов имеет ровно один вердикт. Пересчёт по новой версии создаёт **новый**
    вердикт, не затирая старый: прошлые решения обязаны оставаться объяснимыми.
    """
    decision = computed.decision
    payload = {
        "project_id": project.id,
        "ruleset_id": ruleset.id,
        "group": decision.group,
        "score": decision.score,
        "reasons": {"checks": decision.reasons_json(), "sort_key": decision.sort_key},
        "point_a": _point_json(computed.point_a),
        "point_b": _point_json(computed.point_b),
    }
    stmt = insert(Verdict).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_verdict_project_ruleset",
        set_={
            "group": stmt.excluded.group,
            "score": stmt.excluded.score,
            "reasons": stmt.excluded.reasons,
            "point_a": stmt.excluded.point_a,
            "point_b": stmt.excluded.point_b,
        },
    )
    await session.execute(stmt)
    project.status = ProjectStatus.CLASSIFIED


def _point_json(point: points_module.Point) -> dict[str, object]:
    return {
        "at": point.at.isoformat(),
        "months_used": point.months_used,
        "values": {metric.value: value for metric, value in point.values.items()},
        "derived": dict(point.derived),
    }
