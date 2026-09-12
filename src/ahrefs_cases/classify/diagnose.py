"""Диагностика «плохих»: что просело, когда началось, потеряны ли домены.

По ТЗ «плохим» кейс не формируется, но нужен список с краткой причиной для
внутреннего анализа. Причина — не повторение вердикта («рост ниже порога»), а
факты серии: когда был пик, насколько от него упали, сколько месяцев падение
длилось.

**Правило простое нарочно.** Пик — максимум серии после старта работ; снижение
— то, что после пика; начало снижения — следующий за пиком месяц. Никакой
статистики точек перелома: на калибровке с диагнозом спорят, и вывод обязан
воспроизводиться человеком по двенадцати числам, а не ссылкой на алгоритм.

Три исхода, а не два: **упал**, **не рос** и **не менялся**. Их легко слить в
«нет роста», но действия у них разные — у первого ищут, что сломалось в
конкретный месяц, у второго спрашивают, те ли работы велись, третий чаще всего
означает мёртвый или технический домен.

Модуль ничего не пишет и никуда не ходит: считает по уже собранным сериям.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.series import MetricSeries, load_series
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

FLAT_TOLERANCE_PCT = 2.0
"""Насколько серия может колебаться, чтобы считаться неизменной.

Два процента — не порог группы и не предмет калибровки: это ширина шума, ниже
которой говорить «упал» или «вырос» нечестно. Пороги групп живут версией и
утверждаются людьми (`config/thresholds.*`); здесь же — граница между «есть
движение» и «его нет», и она нужна, чтобы не выдавать за падение колебание в
полпроцента.
"""


class TrafficVerdict(StrEnum):
    """Что случилось с трафиком после старта работ."""

    DROPPED = "dropped"
    """Был пик, после него снижение: ищем, что произошло в конкретный месяц."""

    NO_GROWTH = "no_growth"
    """Рост есть, но слабый: вопрос не «что сломалось», а «те ли работы велись»."""

    FLAT = "flat"
    """Серия не менялась: чаще всего мёртвый или технический домен."""

    NO_DATA = "no_data"
    """Серии после старта работ нет: диагностировать нечего."""


@dataclass(frozen=True, slots=True)
class TrafficDiagnosis:
    """Факты о трафике, по которым человек делает вывод сам."""

    verdict: TrafficVerdict
    peak_at: date | None = None
    peak_value: float | None = None
    last_value: float | None = None
    drop_pct: float | None = None
    decline_months: int = 0
    """Сколько месяцев подряд серия шла вниз после пика."""

    def describe(self) -> str:
        """Диагноз словами, с числами, по которым его можно перепроверить."""
        if self.verdict is TrafficVerdict.NO_DATA:
            return "данных после старта работ нет — диагностировать нечего"
        if self.verdict is TrafficVerdict.FLAT:
            return f"трафик не менялся (около {self.last_value:.0f} за весь период)"
        if self.verdict is TrafficVerdict.NO_GROWTH:
            return (
                f"падения не было: трафик вырос до {self.last_value:.0f}, "
                "но роста не хватило на группу выше"
            )
        started = _next_month(self.peak_at) if self.peak_at else None
        when = started.strftime("%Y-%m") if started else "?"
        peak = self.peak_at.strftime("%Y-%m") if self.peak_at else "?"
        return (
            f"падение с {when}: пик {self.peak_value:.0f} в {peak}, "
            f"к концу периода {self.last_value:.0f} — минус {self.drop_pct:.0f} %, "
            f"снижение длилось {self.decline_months} мес."
        )


@dataclass(frozen=True, slots=True)
class RefdomainsDiagnosis:
    """Что со ссылающимися доменами. `bought=False` — их историю не покупали."""

    bought: bool
    first: float | None = None
    last: float | None = None

    def describe(self) -> str:
        if not self.bought:
            # Молчание здесь читалось бы как «со ссылками всё в порядке», а это
            # ровно тот случай, где ответ стоит денег (урок L30).
            return (
                "позиции и ссылки по проекту не покупались: шаг 2 платится "
                "только кандидатам в кейсы, а «плохие» в них не попадают "
                "(история ссылок — около 95 units на домен)"
            )
        if self.first is None or self.last is None:
            return "история ссылок есть, но пуста"
        delta = self.last - self.first
        if delta < 0:
            return f"потеряно доменов: {self.first:.0f} → {self.last:.0f} ({delta:.0f})"
        if delta == 0:
            return f"ссылающиеся домены не менялись: {self.last:.0f}"
        return f"ссылающиеся домены росли: {self.first:.0f} → {self.last:.0f} (+{delta:.0f})"


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """Краткий разбор одного «плохого» проекта."""

    domain: str
    traffic: TrafficDiagnosis
    refdomains: RefdomainsDiagnosis

    def as_lines(self) -> list[str]:
        return [
            f"{self.domain}: {self.traffic.describe()}",
            f"  ссылки — {self.refdomains.describe()}",
        ]


def diagnose_traffic(series: MetricSeries, period_start: date) -> TrafficDiagnosis:
    """Что случилось с органическим трафиком после старта работ.

    Считается по месяцам **после старта работ**: до него шли чужие результаты,
    и приписывать их этим работам нельзя ни в плюс, ни в минус.
    """
    by_month = {
        month: value
        for month, value in sorted(series.get(Metric.ORG_TRAFFIC, {}).items())
        if month >= period_start
    }
    if not by_month:
        return TrafficDiagnosis(verdict=TrafficVerdict.NO_DATA)

    months = list(by_month)
    values = [by_month[month] for month in months]
    peak_index = values.index(max(values))
    peak_at, peak_value = months[peak_index], values[peak_index]
    last_value = values[-1]
    spread_pct = _pct(max(values) - min(values), max(values))

    if spread_pct <= FLAT_TOLERANCE_PCT:
        return TrafficDiagnosis(
            verdict=TrafficVerdict.FLAT, last_value=last_value, peak_value=peak_value
        )

    drop_pct = _pct(peak_value - last_value, peak_value)
    if drop_pct <= FLAT_TOLERANCE_PCT:
        # Пик в самом конце (или почти) — это не падение, а слабый рост.
        # Выдать его за падение значит отправить человека искать поломку в
        # месяце, в котором ничего не ломалось.
        return TrafficDiagnosis(
            verdict=TrafficVerdict.NO_GROWTH,
            peak_at=peak_at,
            peak_value=peak_value,
            last_value=last_value,
        )

    return TrafficDiagnosis(
        verdict=TrafficVerdict.DROPPED,
        peak_at=peak_at,
        peak_value=peak_value,
        last_value=last_value,
        drop_pct=drop_pct,
        decline_months=len(months) - peak_index - 1,
    )


def diagnose_refdomains(series: MetricSeries) -> RefdomainsDiagnosis:
    """Потеряны ли ссылающиеся домены — если их историю вообще покупали."""
    by_month = series.get(Metric.REFDOMAINS, {})
    if not by_month:
        return RefdomainsDiagnosis(bought=False)
    months = sorted(by_month)
    return RefdomainsDiagnosis(bought=True, first=by_month[months[0]], last=by_month[months[-1]])


def diagnose(domain: str, series: MetricSeries, period_start: date) -> Diagnosis:
    """Разбор одного проекта по уже собранным сериям."""
    return Diagnosis(
        domain=domain,
        traffic=diagnose_traffic(series, period_start),
        refdomains=diagnose_refdomains(series),
    )


def _pct(part: float, whole: float) -> float:
    return 0.0 if whole == 0 else part / whole * 100


def _next_month(anchor: date) -> date:
    total = anchor.year * 12 + anchor.month
    return date(total // 12, total % 12 + 1, 1)


async def diagnose_poor(session: AsyncSession, *, source: MetricSource) -> list[Diagnosis]:
    """Разбор всех «плохих» по действующей версии порогов.

    Чтение живёт здесь же, а не в отдельном модуле: правило диагноза — чистые
    функции выше, а это сорок строк доставки данных, и разносить их по файлам
    значило бы завести модуль без собственной мысли.

    Порядок — по домену: два запуска подряд должны давать одинаковый список,
    иначе его не сравнить глазами. Ничего не пишет и никуда не ходит.
    """
    stmt = (
        select(Project)
        .join(Verdict, Verdict.project_id == Project.id)
        .join(Ruleset, Ruleset.id == Verdict.ruleset_id)
        .where(Ruleset.is_active.is_(True), Verdict.group == Group.POOR)
        .order_by(Project.domain)
    )
    projects = (await session.execute(stmt)).scalars().all()
    return [
        diagnose(
            project.domain,
            await load_series(session, project.id, source),
            project.period_start,
        )
        for project in projects
    ]


async def diagnose_domain(
    session: AsyncSession, domain: str, *, source: MetricSource
) -> Diagnosis | None:
    """Разбор одного проекта независимо от его группы.

    Группа здесь не проверяется намеренно: спросить «что с этим доменом» могут
    и про «средний» — диагноз от этого не становится неверным, он просто
    показывает, что роста хватило.
    """
    project = (
        (await session.execute(select(Project).where(Project.domain == domain))).scalars().first()
    )
    if project is None:
        return None
    return diagnose(
        project.domain, await load_series(session, project.id, source), project.period_start
    )
