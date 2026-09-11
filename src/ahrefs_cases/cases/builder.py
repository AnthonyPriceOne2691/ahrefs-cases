"""Вердикт + серии → структура кейса.

Главное правило модуля: **числа А → Б берутся из записанного вердикта**, а не
считаются заново. Формула точек живёт в `classify/points.py`, формула дельт — в
`classify/deltas.py`; вторая копия любой из них разойдётся с первой ровно тогда,
когда пороги пересчитают новой версией, и клиент увидит в PDF не то число, по
которому проект попал в «хорошие». Поэтому `build_case` серию не принимает
вовсе: границы ему брать неоткуда, кроме вердикта.

Серия читается для другого — сказать, что вердикт от неё отстал
(`stale_subjects`). Сборка детерминирована вердиктом, Ahrefs не трогается, в
базу ничего не пишется.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases.model import (
    CASE_SUBJECTS,
    KW_TOTAL,
    CaseAttempt,
    CaseData,
    CaseOutcome,
    CaseReport,
    Change,
    Period,
)
from ahrefs_cases.classify.deltas import between
from ahrefs_cases.classify.points import Point
from ahrefs_cases.classify.recalc import ruleset_by_version
from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.classify.series import MetricSeries, load_series
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.verdict import Verdict

CASE_GROUPS = frozenset({Group.GOOD, Group.MEDIUM})
"""Кому положен кейс. Шаблон у «хороших» и «средних» пока один — решение ТЗ,
а не упрощение."""

_KEYWORD_BUCKETS = (
    Metric.KW_TOP3,
    Metric.KW_TOP4_10,
    Metric.KW_TOP11_20,
    Metric.KW_TOP21_50,
    Metric.KW_TOP51_PLUS,
)
_METRIC_SUBJECTS = frozenset(metric.value for metric in Metric)
"""Ключи кейса, за которыми стоит купленная метрика. Производные («топ-10»,
«число ключей») в него не входят: их никто не покупал, мы их посчитали."""


class VerdictFormatError(ValueError):
    """Точка вердикта не той формы, что писал `classify/verdicts.store`.

    Отдельная ошибка, а не `.get` с умолчанием: пустая точка и точка с чужими
    ключами выглядели бы одинаково — кейсом без чисел (урок L23).
    """


@dataclass(frozen=True, slots=True)
class VerdictView:
    """Вердикт в том виде, в каком его читает кейс."""

    group: Group
    ruleset_version: str
    point_a: Point
    point_b: Point

    @classmethod
    def of(cls, verdict: Verdict, version: str) -> VerdictView:
        """Версией, а не строкой `Ruleset`: кейсу нужно её имя, а не пороги."""
        return cls(
            group=verdict.group,
            ruleset_version=version,
            point_a=_point_from_json(verdict.point_a),
            point_b=_point_from_json(verdict.point_b),
        )


def build_case(project: Project, verdict: VerdictView) -> CaseData:
    """Структура кейса по одному проекту. Чистая функция: база уже прочитана."""
    changes = _changes(verdict)
    anonymized = not project.publishable
    return CaseData(
        title=_title(project, anonymized=anonymized),
        anonymized=anonymized,
        geo=project.geo,
        niche=project.niche,
        service=project.service_type,
        period=Period(start=project.period_start, end=project.period_end),
        work_volume=project.work_volume,
        group=verdict.group,
        ruleset_version=verdict.ruleset_version,
        changes=changes,
    )


def _title(project: Project, *, anonymized: bool) -> str:
    """Как называем проект. Непубличный не называем никак, кроме ниши.

    Домен не должен попасть в анонимный кейс ни в заголовке, ни в подписи
    графика, ни в имени файла — поэтому решение принимается один раз здесь, а
    рендеры получают готовый заголовок.
    """
    return f"сайт в нише {project.niche}" if anonymized else project.domain


def _changes(verdict: VerdictView) -> tuple[Change, ...]:
    """Изменения А → Б по метрикам, которые есть в **обеих** точках.

    Метрика, появившаяся только к концу периода, в кейс не попадает: сравнивать
    её не с чем, и подставить ноль значило бы объявить рост. Правило то же, что
    у дельт классификации, — потому что это и есть они.
    """
    deltas = between(_with_keywords_total(verdict.point_a), _with_keywords_total(verdict.point_b))
    by_subject = {metric.value: delta for metric, delta in deltas.by_metric.items()}
    by_subject.update(deltas.derived)
    return tuple(
        Change(subject=subject, delta=by_subject[subject])
        for subject in CASE_SUBJECTS
        if subject in by_subject
    )


def _with_keywords_total(point: Point) -> Point:
    """Добавить к точке «число ключей» — сумму пяти корзин распределения.

    Считается, только если есть **все пять**: сумма четырёх корзин выглядит как
    число ключей, но им не является, и занижение никак не видно в кейсе.
    Корзины не покупали — метрики в кейсе просто нет (урок L30).
    """
    if any(bucket not in point.values for bucket in _KEYWORD_BUCKETS):
        return point
    total = sum(point.values[bucket] for bucket in _KEYWORD_BUCKETS)
    return Point(
        at=point.at,
        values=point.values,
        derived={**point.derived, KW_TOTAL: total},
        months_used=point.months_used,
    )


def stale_subjects(verdict: VerdictView, series: MetricSeries) -> tuple[str, ...]:
    """Метрики, купленные после того, как вынесли вердикт.

    Нормальный порядок прогона даёт это сам: ступень кейса докупает DR и
    стоимость трафика только кандидатам, то есть **после** классификации. Числа
    в базе есть, в точках вердикта их нет, и кейс их не покажет. Ответ — не
    вторая формула границ внутри кейса, а бесплатный пересчёт; но сказать об
    этом обязан кто-то: кейс без строки про DR выглядит просто кейсом.
    """
    known = set(verdict.point_a.values) & set(verdict.point_b.values)
    return tuple(
        subject
        for subject in CASE_SUBJECTS
        if subject in _METRIC_SUBJECTS
        and series.get(Metric(subject))
        and Metric(subject) not in known
    )


def _point_from_json(payload: Mapping[str, Any]) -> Point:
    """Точка вердикта из JSONB — строго по форме, которой её записали."""
    try:
        values = payload["values"]
        derived = payload["derived"]
        return Point(
            at=date.fromisoformat(str(payload["at"])),
            values={Metric(key): float(value) for key, value in values.items()},
            derived={str(key): float(value) for key, value in derived.items()},
            months_used=int(payload["months_used"]),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        message = f"точка вердикта не той формы: {exc}"
        raise VerdictFormatError(message) from exc


async def build_cases(
    session: AsyncSession,
    *,
    domain: str | None = None,
    version: str | None = None,
    source: MetricSource = MetricSource.FIXTURE,
) -> CaseReport:
    """Собрать кейсы по вердиктам версии порогов — по умолчанию действующей.

    Ничего не пишет и никуда не ходит: запись кейса приезжает вместе с текстом,
    а Ahrefs здесь нечего спрашивать — всё уже куплено ступенью кейса.

    Порядок — по домену: два запуска подряд обязаны давать одинаковый список,
    иначе его не сравнить глазами.
    """
    ruleset = await (ruleset_by_version(session, version) if version else active_ruleset(session))
    projects = await _projects(session, domain)
    verdicts = await _verdicts(session, ruleset.id)
    attempts = [
        await _attempt(session, project, verdicts.get(project.id), ruleset.version, source=source)
        for project in projects
    ]
    return CaseReport(ruleset_version=ruleset.version, attempts=tuple(attempts))


async def _attempt(
    session: AsyncSession,
    project: Project,
    verdict: Verdict | None,
    version: str,
    *,
    source: MetricSource,
) -> CaseAttempt:
    """Один проект: исход и, если кейс положен, сам кейс."""
    if verdict is None:
        return CaseAttempt(domain=project.domain, outcome=CaseOutcome.NO_VERDICT)
    if verdict.group is Group.INSUFFICIENT_DATA:
        return CaseAttempt(domain=project.domain, outcome=CaseOutcome.INSUFFICIENT_DATA)
    if verdict.group not in CASE_GROUPS:
        return CaseAttempt(domain=project.domain, outcome=CaseOutcome.NOT_ELIGIBLE)
    series = await load_series(session, project.id, source)
    view = VerdictView.of(verdict, version)
    return CaseAttempt(
        domain=project.domain,
        outcome=CaseOutcome.BUILT,
        case=build_case(project, view),
        stale_subjects=stale_subjects(view, series),
    )


async def _projects(session: AsyncSession, domain: str | None) -> list[Project]:
    stmt = select(Project).order_by(Project.domain)
    if domain is not None:
        stmt = stmt.where(Project.domain == domain)
    return list((await session.execute(stmt)).scalars().all())


async def _verdicts(session: AsyncSession, ruleset_id: int) -> dict[int, Verdict]:
    stmt = select(Verdict).where(Verdict.ruleset_id == ruleset_id)
    return {verdict.project_id: verdict for verdict in (await session.execute(stmt)).scalars()}
