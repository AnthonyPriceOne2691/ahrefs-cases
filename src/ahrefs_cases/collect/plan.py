"""План сбора: какие запросы к каким доменам — и каких запросов не будет.

Планировщик отвечает на три вопроса сразу: **как** покупать историю проекта
(`collect/scheme.py`), что спросить у Ahrefs и что уже куплено. Третье — не
оптимизация внутри исполнителя, а часть плана: смета считается до старта, и она
обязана видеть кэш (пример C5).

Границы периода и выбор схемы живут в `scheme.py` — это правило предметной
области («сколько истории нужно кейсу» и «во что она обойдётся»), чистое и
проверяемое таблицей. Чтение того, что уже собрано, живёт здесь, и это
единственное место плана, которому нужна сессия.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from ahrefs_cases.collect.scheme import (
    CollectScheme,
    PointWindows,
    SchemeBreakdown,
    SchemeChoice,
    Window,
    breakdown,
    choose_scheme,
)
from ahrefs_cases.config.ahrefs import CollectSchemeMode
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.project import Project


@dataclass(frozen=True, slots=True)
class CollectTask:
    """Один запрос: проект, endpoint, параметры."""

    project_id: int
    domain: str
    spec: EndpointSpec
    request: HistoryRequest

    def expected_rows(self) -> int:
        """Сколько строк вернёт запрос: по одной на месяц окна.

        От этого зависит цена — биллинг построчный (замерено в Ф7). Смета,
        считающая «50 за запрос», занижала расход в девять раз.
        """
        end = self.request.date_to or self.request.date_from
        return Window(date_from=self.request.date_from, date_to=end).rows

    def estimated_units(self) -> int:
        """Цена этой задачи по модели стоимости."""
        return self.spec.estimate_units(self.expected_rows())


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
    """Что будет запрошено, что сэкономлено и какой схемой.

    `choices` — по одному решению на пару **«проект + endpoint»**: схема
    выбирается на endpoint, потому что у одного проекта `keywords-history`
    выгодно брать точками, а `refdomains-history` историей. Задача при этом не
    единица счёта: в схеме «две точки» их две на пару, и разбивка по задачам
    дала бы «проектов 30, собрано 90» (урок L13).
    """

    tasks: list[CollectTask]
    cached: list[CachedTask]
    choices: Mapping[tuple[int, str], SchemeChoice]

    def estimated_units(self) -> int:
        """Смета: только по задачам, которые действительно уйдут в Ahrefs.

        Цена каждой задачи зависит от глубины окна, а не одинакова: запрос за
        три месяца стоит 63 units, за двадцать один — 441, а окно точки — 50.
        """
        return sum(task.estimated_units() for task in self.tasks)

    def scheme_breakdown(self) -> SchemeBreakdown:
        """Смета в разрезе «endpoint + способ» — для отчёта и экрана Ф6."""
        units: dict[tuple[int, str], int] = {}
        for task in self.tasks:
            key = (task.project_id, task.spec.name)
            units[key] = units.get(key, 0) + task.estimated_units()
        return breakdown(self.choices, units)


async def build_stage1_plan(
    session: AsyncSession,
    projects: Sequence[Project],
    *,
    source: MetricSource,
    now: date,
    refresh: bool = False,
    windows: PointWindows | None = None,
) -> CollectPlan:
    """План шага 1: `metrics-history` всем проектам списка, схемой из конфига."""
    return await build_plan(
        session,
        projects,
        STAGE1_SPECS,
        source=source,
        now=now,
        refresh=refresh,
        windows=windows,
        mode=config.ahrefs.collect_scheme,
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
    windows: PointWindows | None = None,
) -> CollectPlan:
    """План шага 2: дорогие метрики только по переданным проектам.

    Кто попал в список, решает вызывающий (`funnel.preliminary_candidates`, а
    с Ф3 — классификация). Планировщик не выбирает кандидатов сам: иначе
    правило отбора оказалось бы в двух местах и разошлось бы.

    Схема выбирается по цене **на каждый endpoint**, и флага здесь нет:
    флаг шага 1 существует из-за Z6 — дыры в серии трафика, — а правило
    достоверности серии считает `max_gap_months` только по `org_traffic`.
    Разреженность подтверждающих метрик вердикту не мешает, запрещать нечего.

    Решения получаются противоположными на одном и том же периоде, и это
    следствие цены строки, а не свойство endpoint'ов: у `keywords-history`
    пять биллингуемых полей (строка 51) — 204 точками против 918 историей; у
    `refdomains-history` строка стоит 5, и минимум за запрос делает историю
    дешевле — 90 против 100.
    """
    return await build_plan(
        session,
        projects,
        stage2_specs(),
        source=source,
        now=now,
        refresh=refresh,
        windows=windows,
        mode="auto",
    )


async def build_plan(
    session: AsyncSession,
    projects: Sequence[Project],
    specs: Sequence[EndpointSpec],
    *,
    source: MetricSource,
    now: date,
    refresh: bool = False,
    windows: PointWindows | None = None,
    mode: CollectSchemeMode = "history",
) -> CollectPlan:
    """План по набору endpoint'ов с учётом того, что уже куплено.

    `refresh=True` игнорирует кэш целиком — на случай, когда Ahrefs пересчитал
    историю задним числом. По умолчанию выключен: иначе экономия исчезает от
    одного забытого флага.
    """
    asked = windows or PointWindows()
    tasks: list[CollectTask] = []
    cached: list[CachedTask] = []
    choices: dict[tuple[int, str], SchemeChoice] = {}
    for project in projects:
        skip_reason = await _skip_reason(session, project, refresh=refresh)
        for spec in specs:
            choice = _choice_for(project, spec, asked, mode=mode)
            choices[(project.id, spec.name)] = choice
            if skip_reason is not None:
                cached.append(_cached(project, spec, skip_reason))
                continue
            planned, saved = await _tasks_for_spec(
                session, project, spec, choice, source=source, now=now, refresh=refresh
            )
            tasks.extend(planned)
            cached.extend(saved)
    return CollectPlan(tasks=tasks, cached=cached, choices=choices)


def _choice_for(
    project: Project,
    spec: EndpointSpec,
    asked: PointWindows,
    *,
    mode: CollectSchemeMode,
) -> SchemeChoice:
    """Решение по паре «проект + endpoint».

    Схема применяется к каждому запросу отдельно, поэтому и считается отдельно:
    одно решение по сумме цен разных endpoint'ов было бы неправдой для каждого
    из них. На шаге 1 набор из одного endpoint'а, и разницы не видно; на шаге 2
    решения противоположны.

    Запас до старта работ складывается из двух слагаемых: сколько просят пороги
    (`pre_start_baseline_months` — расчёт baseline'а Ф3б) и сколько добавлено
    конфигом. Раньше три месяца брались безусловно и стоили 33 units на домен,
    а читателя у них не было ни одного.
    """
    return choose_scheme(
        period_start=project.period_start,
        period_end=project.period_end,
        spec=spec,
        windows=PointWindows(
            point_months=asked.point_months,
            baseline_months=asked.baseline_months + config.ahrefs.history_lead_months,
        ),
        max_history_months=config.ahrefs.max_history_months,
        mode=mode,
    )


async def _tasks_for_spec(
    session: AsyncSession,
    project: Project,
    spec: EndpointSpec,
    choice: SchemeChoice,
    *,
    source: MetricSource,
    now: date,
    refresh: bool,
) -> tuple[list[CollectTask], list[CachedTask]]:
    """Задачи одного endpoint'а по выбранной схеме, с учётом кэша.

    Кэш спрашивается по-разному, и это не непоследовательность, а следствие
    цены. У истории есть смысл сузить окно: цена растёт со строками. У окна
    точки — нет: запрос на один месяц и на четыре стоят одинаково (минимум 50),
    поэтому окно либо куплено целиком, либо покупается целиком заново.
    """
    tasks: list[CollectTask] = []
    cached: list[CachedTask] = []
    metrics = tuple(spec.metrics.values())
    for window in choice.windows:
        asked_window = window
        if choice.scheme is CollectScheme.FULL_HISTORY:
            date_from = await _incremental_from(
                session, project, metrics, window, source=source, now=now, refresh=refresh
            )
            if date_from is None:
                cached.append(_cached(project, spec))
                continue
            asked_window = Window(date_from=date_from, date_to=window.date_to)
        elif not refresh and await cache.window_is_covered(
            session,
            project.id,
            metrics,
            source,
            window_from=window.date_from,
            window_to=window.date_to,
            now=now,
        ):
            cached.append(_cached(project, spec, f"окно {window.date_from:%Y-%m} уже куплено"))
            continue
        tasks.append(
            CollectTask(
                project_id=project.id,
                domain=project.domain,
                spec=spec,
                request=HistoryRequest(
                    target=project.domain,
                    mode=project.target_mode,
                    country=project.geo,
                    date_from=asked_window.date_from,
                    date_to=asked_window.date_to,
                ),
            )
        )
    return tasks, cached


def _cached(project: Project, spec: EndpointSpec, reason: str | None = None) -> CachedTask:
    if reason is None:
        return CachedTask(project_id=project.id, domain=project.domain, spec=spec)
    return CachedTask(project_id=project.id, domain=project.domain, spec=spec, reason=reason)


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
    metrics: Sequence[Metric],
    window: Window,
    *,
    source: MetricSource,
    now: date,
    refresh: bool,
) -> date | None:
    if refresh:
        return window.date_from
    known = await cache.coverage(session, project.id, metrics, source)
    return cache.next_date_from(
        known,
        window_from=window.date_from,
        window_to=window.date_to,
        now=now,
        fresh=cache.is_fresh(known.fetched_at),
    )
