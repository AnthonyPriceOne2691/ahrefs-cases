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
from datetime import date
from typing import Any

from ahrefs_cases.classify.deltas import Deltas
from ahrefs_cases.classify.points import Point
from ahrefs_cases.classify.thresholds import GroupRule, Thresholds, Windows
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


@dataclass(frozen=True, slots=True)
class Evidence:
    """Чем считали вердикт: начало истории, границы периода и чего не хватило.

    Собрано в один объект не ради красоты: у `decide` стало девять аргументов, и
    гейт сложности прав — это не список параметров, а описание одного предмета.
    Все четыре поля отвечают на один вопрос — «насколько полны данные, по
    которым посчитан вердикт», и меняются вместе.

    Пустое `Evidence()` — законный случай: правила проверяются и на голых
    дельтах, без сведений о покрытии.
    """

    point_a: Point | None = None
    history_starts_at: date | None = None
    period_start: date | None = None
    unbought: str = ""
    """Месяцы, которых версия порогов просит, а никто не покупал."""


def decide(
    deltas: Deltas,
    point_b: Point,
    *,
    months_after_start: int,
    max_gap_months: int,
    thresholds: Thresholds,
    evidence: Evidence | None = None,
) -> Decision:
    """Вердикт по проекту. Чистая функция: ни базы, ни сети, ни времени.

    `evidence` — чем считали: точка А, начало истории, границы периода и
    непокупленные месяцы (`classify/coverage.py`). Последние делают вердикт
    невозможным, а не неточным:
    точка считается по тем месяцам окна, которые есть, и вердикт по половине
    окна выглядит настоящим. Приходит строкой, потому что правило не про
    арифметику дельт, а про то, что человеку **делать** — докупить.
    """
    facts = evidence or Evidence()
    blockers = _eligibility(deltas, point_b, months_after_start, max_gap_months, thresholds)
    short_windows = _short_windows(facts.point_a, point_b, thresholds.windows)
    if facts.unbought:
        blockers.append(
            Reason(
                subject="unbought_months",
                fact=None,
                threshold=None,
                passed=False,
                note=f"не куплены месяцы, которые просит версия порогов — {facts.unbought}",
            )
        )
    truncated = [
        *_truncated_history(facts.history_starts_at, facts.period_start),
        *short_windows,
    ]
    if blockers:
        return Decision(group=Group.INSUFFICIENT_DATA, score=0.0, reasons=[*blockers, *truncated])

    traffic = deltas.metric(_TRAFFIC)
    if traffic is None:  # pragma: no cover — отсечено eligibility выше
        message = "нет дельты трафика после проверки пригодности"
        raise AssertionError(message)

    good_reasons = _check_group(deltas, thresholds.good, months_after_start, name="good")
    if _satisfied(good_reasons):
        return _decided(Group.GOOD, [*good_reasons, *truncated], deltas, thresholds)

    medium_reasons = _check_group(deltas, thresholds.medium, months_after_start, name="medium")
    if _satisfied(medium_reasons):
        return _decided(
            Group.MEDIUM, [*good_reasons, *medium_reasons, *truncated], deltas, thresholds
        )

    return _decided(Group.POOR, [*good_reasons, *medium_reasons, *truncated], deltas, thresholds)


def _short_windows(point_a: Point | None, point_b: Point, windows: Windows) -> list[Reason]:
    """Точка посчитана не по всему окну — сказать, по скольким месяцам.

    Отсутствующий месяц окна не обнуляет точку, а просто не участвует в среднем
    (`points._average`). Для дыры в данных Ahrefs это правильно, но человеку
    нужно знать: «рост 151 %» по одному месяцу из двух и по двум из двух — не
    одно и то же утверждение.

    Молчания здесь не было заметно, пока о том же случае говорило правило
    покрытия — оно просто **запрещало** вердикт. Когда 13.09.2026 запрет сняли
    (месяц внутри периода — свойство данных Ahrefs, а не пробел в покупке),
    оказалось, что сказать об усечённом окне больше некому:
    `_truncated_history` молчит при отставании в один месяц, а окно точки как
    раз два. Запись справочная — группу она не меняет.
    """
    reasons: list[Reason] = []
    for point, asked, name in (
        (point_a, windows.point_a_months, "point_a_months_used"),
        (point_b, windows.point_b_months, "point_b_months_used"),
    ):
        if point is None or asked <= 0 or point.months_used >= asked or point.months_used == 0:
            continue
        reasons.append(
            Reason(
                subject=name,
                fact=float(point.months_used),
                threshold=float(asked),
                passed=True,
                note=f"точка посчитана по {point.months_used} мес. из {asked}: "
                "остальных месяцев окна нет в данных Ahrefs",
                decisive=False,
            )
        )
    return reasons


def _truncated_history(history_starts_at: date | None, period_start: date | None) -> list[Reason]:
    """История начинается позже старта работ — точка А не про старт.

    Так бывает, когда период работ длиннее доступной глубины
    (`AHREFS_MAX_HISTORY_MONTHS` минус запас) или когда Ahrefs просто не знает
    домен так давно. Молчать об этом нельзя: точка А тогда взята не от начала
    работ, и «рост А → Б» отвечает на другой вопрос, чем думает читатель кейса.

    Запись справочная — группу она не меняет. Решать, годится ли такой кейс,
    будет человек, а его дело — узнать (Z5 в docs/FINDINGS.md).
    """
    if history_starts_at is None or period_start is None:
        return []
    months_late = (history_starts_at.year - period_start.year) * 12 + (
        history_starts_at.month - period_start.month
    )
    if months_late <= 1:
        return []
    return [
        Reason(
            subject="history_truncated",
            fact=float(months_late),
            threshold=1.0,
            passed=False,
            note=(
                "история начинается позже старта работ: точка А посчитана не от начала "
                "периода, и «рост А → Б» описывает не весь срок работ"
            ),
            decisive=False,
        )
    ]


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
