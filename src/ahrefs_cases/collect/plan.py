"""План сбора: какие запросы к каким доменам.

Ф2а планирует **шаг 1** воронки — `metrics-history` всем проектам. Шаг 2
(`keywords-history`, `refdomains-history`, срезы) приходит в Ф2б: отбирать
кандидатов нечем, пока нет предварительной группы, а платить за дорогие метрики
по «плохим» проектам — ровно то, чего воронка избегает.

Границы периода запроса считаются здесь, а не в исполнителе: это правило
предметной области («сколько истории нужно кейсу»), и проверять его надо без
базы и без провайдера.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ahrefs_cases import config
from ahrefs_cases.collect.endpoints import STAGE1_SPECS, EndpointSpec
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.storage.models.project import Project


@dataclass(frozen=True, slots=True)
class CollectTask:
    """Один запрос: проект, endpoint, параметры."""

    project_id: int
    domain: str
    spec: EndpointSpec
    request: HistoryRequest


def plan_stage1(projects: Sequence[Project]) -> list[CollectTask]:
    """Задачи шага 1 — по одной на проект."""
    return [
        CollectTask(
            project_id=project.id,
            domain=project.domain,
            spec=spec,
            request=history_request(project),
        )
        for project in projects
        for spec in STAGE1_SPECS
    ]


def history_request(project: Project) -> HistoryRequest:
    """Границы истории для проекта.

    Начало — на `history_lead_months` раньше старта работ: точка А считается
    средним по окну вокруг границы, и без запаса окно упирается в первый месяц
    данных. Конец — `period_end` проекта, а не «сегодня»: кейс не должен меняться
    от даты пересборки.
    """
    return HistoryRequest(
        target=project.domain,
        mode=project.target_mode,
        country=project.geo,
        date_from=_history_from(project.period_start, project.period_end),
        date_to=project.period_end,
    )


def _history_from(period_start: date, period_end: date) -> date:
    """Старт работ минус запас, но не глубже `max_history_months` от конца.

    Ограничение сверху — не экономия, а честность: на тарифе Advanced глубина
    истории конечна, и просить сорок месяцев значит получить меньше и не знать,
    что получил меньше. Реальную глубину покажет Ф7.
    """
    lead = _shift_months(period_start, -config.ahrefs.history_lead_months)
    floor = _shift_months(period_end, -config.ahrefs.max_history_months)
    return max(lead, floor)


def _shift_months(anchor: date, months: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)
