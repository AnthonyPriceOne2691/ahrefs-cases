"""План сбора: какие запросы к каким доменам — и каких запросов не будет.

Планировщик отвечает на два вопроса сразу: что спросить у Ahrefs и что уже
куплено. Второе — не оптимизация внутри исполнителя, а часть плана: смета
считается до старта, и она обязана видеть кэш (пример C5).

Границы периода — чистые функции без базы и провайдера: это правило предметной
области («сколько истории нужно кейсу»). Чтение того, что уже собрано, живёт в
`build_stage1_plan`, и это единственное место плана, которому нужна сессия.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect import cache
from ahrefs_cases.collect.endpoints import (
    DOMAIN_RATING_HISTORY,
    PAGES_HISTORY,
    STAGE1_SPECS,
    STAGE2_SPECS,
    TOTAL_SEARCH_VOLUME_HISTORY,
    EndpointSpec,
)
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.storage._enums import MetricSource
from ahrefs_cases.storage.models.project import Project


@dataclass(frozen=True, slots=True)
class CollectTask:
    """Один запрос: проект, endpoint, параметры."""

    project_id: int
    domain: str
    spec: EndpointSpec
    request: HistoryRequest


@dataclass(frozen=True, slots=True)
class CachedTask:
    """Запрос, которого не будет: всё нужное уже в базе.

    Хранится наравне с задачами, потому что это предъявляемая экономия: строка
    `kind=cached` в журнале и число «запросов сэкономлено» в отчёте берутся
    отсюда. Молчаливый пропуск выглядел бы как «прогон ничего не делал».
    """

    project_id: int
    domain: str
    spec: EndpointSpec
    reason: str = "вся история уже собрана"


@dataclass(frozen=True, slots=True)
class CollectPlan:
    """Что будет запрошено и что сэкономлено."""

    tasks: list[CollectTask]
    cached: list[CachedTask]

    def estimated_units(self) -> int:
        """Смета: только по задачам, которые действительно уйдут в Ahrefs."""
        return sum(task.spec.estimate_units() for task in self.tasks)


def plan_stage1(projects: Sequence[Project]) -> list[CollectTask]:
    """Задачи шага 1 без учёта кэша — полный проход по проектам.

    Остаётся отдельной функцией: она чистая и ею меряется «сколько стоил бы
    прогон без экономии» — то самое число, с которым сравнивают смету.
    """
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


async def build_stage1_plan(
    session: AsyncSession,
    projects: Sequence[Project],
    *,
    source: MetricSource,
    now: date,
    refresh: bool = False,
) -> CollectPlan:
    """План шага 1: `metrics-history` всем проектам списка."""
    return await build_plan(
        session, projects, STAGE1_SPECS, source=source, now=now, refresh=refresh
    )


def stage2_specs() -> tuple[EndpointSpec, ...]:
    """Endpoint'ы шага 2: обязательные плюс включённые флагами.

    Под флагами — те, которых нет ни в правилах Ф3, ни в блоках кейса по ТЗ.
    Каждый стоит как полноценный запрос (50 units за домен), то есть чистая
    надбавка к цене прогона: на тридцати кандидатах это 3000 units, треть
    бюджета первичного прогона за данные без читателя (Z4 в docs/FINDINGS.md).

    Соответствие «endpoint → флаг» написано явно, а не через `getattr` по
    имени поля: доступ к конфигу отражением запрещён правилом проекта и ловится
    гейтом `config-access` — он и поймал первую версию этой функции. Опечатка
    в имени поля при отражении не видна ни mypy, ни на ревью, а стоит она
    здесь трети бюджета.
    """
    enabled: dict[str, bool] = {
        DOMAIN_RATING_HISTORY.name: config.ahrefs.collect_dr_history,
        PAGES_HISTORY.name: config.ahrefs.collect_pages_history,
        TOTAL_SEARCH_VOLUME_HISTORY.name: config.ahrefs.collect_search_volume,
    }
    return tuple(spec for spec in STAGE2_SPECS if enabled.get(spec.name, True))


async def build_stage2_plan(
    session: AsyncSession,
    projects: Sequence[Project],
    *,
    source: MetricSource,
    now: date,
    refresh: bool = False,
) -> CollectPlan:
    """План шага 2: дорогие метрики только по переданным проектам.

    Кто попал в список, решает вызывающий (`funnel.preliminary_candidates`, а
    с Ф3 — классификация). Планировщик не выбирает кандидатов сам: иначе
    правило отбора оказалось бы в двух местах и разошлось бы.
    """
    return await build_plan(
        session, projects, stage2_specs(), source=source, now=now, refresh=refresh
    )


async def build_plan(
    session: AsyncSession,
    projects: Sequence[Project],
    specs: Sequence[EndpointSpec],
    *,
    source: MetricSource,
    now: date,
    refresh: bool = False,
) -> CollectPlan:
    """План по набору endpoint'ов с учётом того, что уже куплено.

    `refresh=True` игнорирует кэш целиком — на случай, когда Ahrefs пересчитал
    историю задним числом. По умолчанию выключен: иначе экономия исчезает от
    одного забытого флага.
    """
    tasks: list[CollectTask] = []
    cached: list[CachedTask] = []
    for project in projects:
        for spec in specs:
            request = history_request(project)
            skip_reason = await _skip_reason(session, project, refresh=refresh)
            if skip_reason is not None:
                cached.append(
                    CachedTask(
                        project_id=project.id,
                        domain=project.domain,
                        spec=spec,
                        reason=skip_reason,
                    )
                )
                continue
            date_from = await _incremental_from(
                session, project, spec, request, source=source, now=now, refresh=refresh
            )
            if date_from is None:
                cached.append(CachedTask(project_id=project.id, domain=project.domain, spec=spec))
                continue
            tasks.append(
                CollectTask(
                    project_id=project.id,
                    domain=project.domain,
                    spec=spec,
                    request=replace(request, date_from=date_from),
                )
            )
    return CollectPlan(tasks=tasks, cached=cached)


async def _skip_reason(session: AsyncSession, project: Project, *, refresh: bool) -> str | None:
    """Причина не спрашивать домен вовсе, помимо «всё уже собрано».

    Пока такая причина одна: по домену уже получали пустую историю недавно.
    Без этой проверки молодой домен покупается заново каждым прогоном — данных
    он не даёт, а стоит столько же, сколько домен с данными.
    """
    if refresh:
        return None
    checked_at = await cache.empty_since(session, project.id)
    if not cache.empty_is_remembered(checked_at):
        return None
    when = checked_at.date().isoformat() if checked_at else "?"
    return f"истории нет, проверено {when} — повтор через {config.ahrefs.empty_retry_days} дн."


async def _incremental_from(
    session: AsyncSession,
    project: Project,
    spec: EndpointSpec,
    request: HistoryRequest,
    *,
    source: MetricSource,
    now: date,
    refresh: bool,
) -> date | None:
    if refresh:
        return request.date_from
    known = await cache.coverage(session, project.id, tuple(spec.metrics.values()), source)
    return cache.next_date_from(
        known,
        window_from=request.date_from,
        window_to=request.date_to or project.period_end,
        now=now,
        fresh=cache.is_fresh(known.fetched_at),
    )


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
