"""Пороги + дельты → группа, объяснение и score.

Каждое условие возвращает запись `Reason`: метрика, факт, порог, сработало или
нет. Объяснение строится **тем же проходом**, что и решение, а не вторым
обходом тех же правил: два места разошлись бы при первой правке порога, и
экран Ф6 показывал бы не то, по чему вынесен вердикт.

`insufficient_data` считается раньше групп: «нет данных» и «плохой результат»
ведут к разным действиям — докупить историю против не делать кейс.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ahrefs_cases.classify.deltas import Deltas
from ahrefs_cases.classify.points import Point
from ahrefs_cases.classify.thresholds import GroupRule, Thresholds
from ahrefs_cases.storage._enums import Group, Metric

_TRAFFIC = Metric.ORG_TRAFFIC


@dataclass(frozen=True, slots=True)
class Reason:
    """Одно проверенное условие в человеческом виде."""

    subject: str
    fact: float | None
    threshold: float | None
    passed: bool
    note: str = ""
    decisive: bool = True
    """Участвует ли условие в решении.

    Записи о конкретных подтверждающих метриках — **не** решающие: сколько их
    нужно, говорит `supporting_required`, и при нулевом требовании
    несработавшая подтверждающая метрика группу не отменяет. Она всё равно
    попадает в объяснение: человеку важно видеть, что ссылочное не выросло,
    даже если группу это не изменило.

    Различение поймано тестом: без него `weak_growth` уходил в `poor`, потому
    что «топ-10 вырос на 12 % при ориентире 15 %» считалось провалом условия,
    которого никто не требовал.
    """

    def as_json(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "fact": self.fact,
            "threshold": self.threshold,
            "passed": self.passed,
            "note": self.note,
            "decisive": self.decisive,
        }


@dataclass(frozen=True, slots=True)
class Decision:
    """Группа, объяснение и score для сортировки."""

    group: Group
    score: float
    reasons: list[Reason] = field(default_factory=list)
    sort_key: float = 0.0
    """Абсолютный прирост трафика: внутри группы сортируем по нему.

    Так закрыто расхождение ответов заказчика — вопрос 28 задаёт порог в
    процентах, вопрос 30 требует приоритета большему абсолютному числу.
    Порог комбинированный, порядок — по абсолюту.
    """

    def reasons_json(self) -> list[dict[str, Any]]:
        return [reason.as_json() for reason in self.reasons]


def decide(
    deltas: Deltas,
    point_b: Point,
    *,
    months_after_start: int,
    max_gap_months: int,
    thresholds: Thresholds,
) -> Decision:
    """Вердикт по проекту. Чистая функция: ни базы, ни сети, ни времени."""
    blockers = _eligibility(deltas, point_b, months_after_start, max_gap_months, thresholds)
    if blockers:
        return Decision(group=Group.INSUFFICIENT_DATA, score=0.0, reasons=blockers)

    traffic = deltas.metric(_TRAFFIC)
    if traffic is None:  # pragma: no cover — отсечено eligibility выше
        message = "нет дельты трафика после проверки пригодности"
        raise AssertionError(message)

    good_reasons = _check_group(deltas, thresholds.good, months_after_start, name="good")
    if _satisfied(good_reasons):
        return _decided(Group.GOOD, good_reasons, deltas, thresholds)

    medium_reasons = _check_group(deltas, thresholds.medium, months_after_start, name="medium")
    if _satisfied(medium_reasons):
        return _decided(Group.MEDIUM, [*good_reasons, *medium_reasons], deltas, thresholds)

    return _decided(Group.POOR, [*good_reasons, *medium_reasons], deltas, thresholds)


def _satisfied(reasons: list[Reason]) -> bool:
    """Группа выполнена, если выполнены все **решающие** условия."""
    return all(reason.passed for reason in reasons if reason.decisive)


def _eligibility(
    deltas: Deltas,
    point_b: Point,
    months_after_start: int,
    max_gap_months: int,
    thresholds: Thresholds,
) -> list[Reason]:
    """Причины, по которым классифицировать нельзя вовсе."""
    rules = thresholds.eligibility
    blockers: list[Reason] = []

    if months_after_start < rules.min_months_after_start:
        blockers.append(
            Reason(
                subject="months_after_start",
                fact=float(months_after_start),
                threshold=float(rules.min_months_after_start),
                passed=False,
                note="слишком короткая история после старта работ",
            )
        )
    if max_gap_months > rules.max_series_gap_months:
        blockers.append(
            Reason(
                subject="series_gap_months",
                fact=float(max_gap_months),
                threshold=float(rules.max_series_gap_months),
                passed=False,
                note="дыра в данных длиннее допустимой — серия недостоверна",
            )
        )
    if deltas.metric(_TRAFFIC) is None:
        blockers.append(
            Reason(
                subject="org_traffic",
                fact=None,
                threshold=None,
                passed=False,
                note="нет трафика в одной из точек: сравнивать не с чем",
            )
        )
    traffic_b = point_b.get(_TRAFFIC)
    if rules.min_traffic_point_b > 0 and (traffic_b or 0.0) < rules.min_traffic_point_b:
        blockers.append(
            Reason(
                subject="traffic_point_b",
                fact=traffic_b,
                threshold=rules.min_traffic_point_b,
                passed=False,
                note="трафик в точке Б ниже минимального для кейса",
            )
        )
    return blockers


def _check_group(
    deltas: Deltas, rule: GroupRule, months_after_start: int, *, name: str
) -> list[Reason]:
    """Условия одной группы: главная метрика, подтверждающие, длительность."""
    traffic = deltas.metric(_TRAFFIC)
    pct = traffic.pct if traffic else None
    absolute = traffic.absolute if traffic else 0.0

    reasons = [
        Reason(
            subject=f"{name}.org_traffic_pct",
            fact=pct,
            threshold=rule.org_traffic.growth_pct_min,
            passed=pct is not None and pct >= rule.org_traffic.growth_pct_min,
            note="рост органического трафика в процентах",
        )
    ]
    if rule.org_traffic.growth_abs_min is not None:
        reasons.append(
            Reason(
                subject=f"{name}.org_traffic_abs",
                fact=absolute,
                threshold=rule.org_traffic.growth_abs_min,
                passed=absolute >= rule.org_traffic.growth_abs_min,
                note="абсолютный прирост визитов в месяц",
            )
        )
    reasons.extend(_supporting(deltas, rule, name=name))
    reasons.append(
        Reason(
            subject=f"{name}.months_after_start",
            fact=float(months_after_start),
            threshold=float(rule.min_months_after_start),
            passed=months_after_start >= rule.min_months_after_start,
            note="месяцев данных после старта работ",
        )
    )
    return reasons


def _supporting(deltas: Deltas, rule: GroupRule, *, name: str) -> list[Reason]:
    """Подтверждающие метрики: ссылочное и позиции.

    В «хорошие» — только при главной метрике **И** минимум одной подтверждающей
    (прямое требование ТЗ). Сколько именно нужно, говорит `supporting_required`
    той же группы: у «средних» оно равно нулю, и это разобрано в спеке —
    иначе проект с сильным ростом трафика и без ссылочного не попадал бы ни в
    одну группу.
    """
    refdomains = deltas.metric(Metric.REFDOMAINS)
    top10 = deltas.top10()
    checks = [
        Reason(
            subject=f"{name}.refdomains_pct",
            fact=refdomains.pct if refdomains else None,
            threshold=rule.supporting.refdomains_growth_pct_min,
            passed=bool(
                refdomains
                and refdomains.pct is not None
                and refdomains.pct >= rule.supporting.refdomains_growth_pct_min
            ),
            note="рост ссылающихся доменов",
            decisive=False,
        ),
        Reason(
            subject=f"{name}.kw_top10_pct",
            fact=top10.pct if top10 else None,
            threshold=rule.supporting.kw_top10_growth_pct_min,
            passed=bool(
                top10
                and top10.pct is not None
                and top10.pct >= rule.supporting.kw_top10_growth_pct_min
            ),
            note="рост числа ключей в топ-10",
            decisive=False,
        ),
    ]
    satisfied = sum(1 for check in checks if check.passed)
    checks.append(
        Reason(
            subject=f"{name}.supporting_required",
            fact=float(satisfied),
            threshold=float(rule.supporting_required),
            passed=satisfied >= rule.supporting_required,
            note="сколько подтверждающих метрик сработало",
        )
    )
    return checks


def _decided(
    group: Group, reasons: list[Reason], deltas: Deltas, thresholds: Thresholds
) -> Decision:
    traffic = deltas.metric(_TRAFFIC)
    return Decision(
        group=group,
        score=_score(deltas, thresholds),
        reasons=reasons,
        sort_key=traffic.absolute if traffic else 0.0,
    )


def _score(deltas: Deltas, thresholds: Thresholds) -> float:
    """Взвешенная оценка «какой из них лучше» внутри группы.

    Группа отвечает на «годится ли в кейс», score — на «покажи топ-N». В
    правилах он не участвует: иначе сумма весов начала бы подменять пороги,
    которые утверждает заказчик.
    """
    weights = thresholds.score.weights
    traffic = deltas.metric(_TRAFFIC)
    refdomains = deltas.metric(Metric.REFDOMAINS)
    top3 = deltas.metric(Metric.KW_TOP3)
    return (
        weights.org_traffic_growth_pct * ((traffic.pct or 0.0) if traffic else 0.0)
        + weights.org_traffic_growth_abs * (traffic.absolute if traffic else 0.0)
        + weights.kw_top3_growth_abs * (top3.absolute if top3 else 0.0)
        + weights.refdomains_growth_pct * ((refdomains.pct or 0.0) if refdomains else 0.0)
    )
