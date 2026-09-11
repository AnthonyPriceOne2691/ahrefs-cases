"""Структура кейса: числа и подписи, готовые к рендеру.

Ни вёрстки, ни текста — только то, что кейс показывает, в виде, одинаковом для
всех форматов: PDF, веб-карточка, будущий PPTX. Числа считаются один раз, иначе
три формата покажут три разных результата по одному проекту.

Два свойства структуры, которые легко потерять: **анонимность — часть кейса, а
не решение рендера** (Q12 ТЗ), и **метрика, которой не покупали, выпадает из
кейса целиком** — не ноль и не пустой график (урок L30).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType

from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.classify.points import KW_TOP10
from ahrefs_cases.storage._enums import Group, Metric

KW_TOTAL = "kw_total"
"""«Число ключей» из must-have списка ТЗ — сумма пяти корзин распределения.

Живёт здесь, а не рядом с `KW_TOP10` в `classify/points.py`, потому что
классификация им не пользуется: в правилах участвует только топ-10. Показывает
его один кейс, и правило показа — его дело.

Гипотеза H7 реестра находок: сумма корзин равна `organic_keywords` Ahrefs.
Замером не подтверждена, проверяется в Ф7 глазами — поэтому подпись честно
говорит «сумма корзин», а не «видимость».
"""

SUBJECT_LABELS: Mapping[str, str] = MappingProxyType(
    {
        Metric.ORG_TRAFFIC.value: "органический трафик",
        KW_TOP10: "ключи в топ-10",
        Metric.KW_TOP3.value: "ключи в топ-3",
        KW_TOTAL: "число ключей (сумма корзин)",
        Metric.REFDOMAINS.value: "ссылающиеся домены",
        Metric.ORG_COST.value: "стоимость трафика, $",
        Metric.DR.value: "Domain Rating",
    }
)
"""Подписи метрик в кейсе, один словарь на все форматы. Подписи нет — метрики
нет: берётся по ключу, а не `.get` с подстановкой имени поля (урок L23)."""

CASE_SUBJECTS: tuple[str, ...] = (
    Metric.ORG_TRAFFIC.value,
    KW_TOP10,
    Metric.KW_TOP3.value,
    KW_TOTAL,
    Metric.REFDOMAINS.value,
    Metric.ORG_COST.value,
    Metric.DR.value,
)
"""Что кейс показывает в блоке «А → Б» и в каком порядке: первой главная
метрика ТЗ, за ней видимость, дальше ссылочное и деньги. Корзины глубже топ-10
поштучно не показываются — они нужны суммой, и сумма это `kw_total`."""


CHART_SUBJECTS: tuple[str, ...] = (Metric.ORG_TRAFFIC.value, KW_TOP10, Metric.KW_TOP3.value)
"""Что показывается кривой. ТЗ называет две динамики — трафика и позиций;
позиции рисуются двумя рядами на одном графике: топ-10 и вложенный в него
топ-3. Ссылающиеся домены остаются числом в таблице: третья кривая съела бы
место, а ТЗ её не просит."""


@dataclass(frozen=True, slots=True)
class CaseSeries:
    """Месячный ряд под кривую — по измеренным точкам, без интерполяции.

    Пропущенный месяц отсутствует и здесь: дорисовать его линией значило бы
    показать клиенту месяц, которого мы не мерили.
    """

    subject: str
    points: tuple[tuple[date, float], ...]

    @property
    def label(self) -> str:
        return SUBJECT_LABELS[self.subject]


class CaseOutcome(StrEnum):
    """Чем закончилась попытка собрать кейс. Исходов четыре, а не два.

    «Не положен по группе», «данных не хватило» и «вердикта нет» ведут к разным
    действиям — ничего не делать, докупить историю, классифицировать, — и
    слияние их в «кейса нет» оставляет человека без следующего шага (L32, L34).
    """

    BUILT = "built"
    NOT_ELIGIBLE = "not_eligible"
    """Группа `poor`: по ТЗ кейс не формируется, формируется диагностика."""

    INSUFFICIENT_DATA = "insufficient_data"
    """Группа `insufficient_data`: вопрос не к результату, а к данным."""

    NO_VERDICT = "no_verdict"
    """Проект не классифицирован этой версией порогов: кейс собирать не из чего."""


@dataclass(frozen=True, slots=True)
class Change:
    """Изменение метрики от А к Б — обёртка вокруг `Delta` классификации, а не
    вторая копия арифметики: кейс показывает ровно её результат."""

    subject: str
    delta: Delta

    @property
    def label(self) -> str:
        return SUBJECT_LABELS[self.subject]

    @property
    def before(self) -> float:
        return self.delta.before

    @property
    def after(self) -> float:
        return self.delta.after

    @property
    def absolute(self) -> float:
        return self.delta.absolute

    @property
    def pct(self) -> float | None:
        """`None` — рост от нулевой базы: процента у него нет."""
        return self.delta.pct

    @property
    def grew(self) -> bool:
        return self.delta.grew


@dataclass(frozen=True, slots=True)
class Period:
    """Период работ. Конец задаёт агентство, даже если работы продолжаются."""

    start: date
    end: date

    @property
    def months(self) -> int:
        """Длительность в месяцах, включая месяцы старта и конца."""
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1


@dataclass(frozen=True, slots=True)
class CaseData:
    """Кейс как данные: блоки ТЗ, изменения А → Б, подсветка и кривые."""

    title: str
    """Домен — или «сайт в нише X», если публиковать имя нельзя."""

    anonymized: bool
    geo: str
    niche: str
    service: str
    period: Period
    work_volume: int | None
    """Объём работ из входного файла. `None` — блока «что сделали» в кейсе нет:
    поле по ТЗ необязательное, и «0 ссылок» было бы выдумкой."""

    group: Group
    ruleset_version: str
    """Версия порогов **того вердикта**, который породил кейс, а не действующей
    сейчас: иначе кейс объяснялся бы порогами, по которым его не выносили."""

    changes: tuple[Change, ...]
    series: tuple[CaseSeries, ...] = ()
    """Ряды под кривые. Пусто — законное состояние: метрик под кривые не
    покупали, и кейс выходит без графиков, а не с пустыми осями."""

    window_a: tuple[date, ...] = ()
    window_b: tuple[date, ...] = ()
    """Месяцы, по которым усреднены точки А и Б.

    Лежат в кейсе, потому что их показывают: последний измеренный месяц кривой
    и точка Б различаются по построению, и рядом на листе это читается как
    ошибка, пока не видно окна.
    """

    def change(self, subject: str) -> Change | None:
        """Изменение по метрике — или `None`, если её в кейсе нет."""
        for change in self.changes:
            if change.subject == subject:
                return change
        return None


@dataclass(frozen=True, slots=True)
class CaseAttempt:
    """Попытка собрать кейс по одному проекту: исход и, если получилось, кейс."""

    domain: str
    outcome: CaseOutcome
    case: CaseData | None = None
    stale_subjects: tuple[str, ...] = ()
    """Метрики, которые куплены, но которых нет в вердикте: он старше данных.
    Почему так выходит на ровном месте — `builder.stale_subjects`."""


@dataclass(frozen=True, slots=True)
class CaseReport:
    """Итог сборки в числах для человека.

    Считает **проекты**, а не строки и не метрики (урок L13), и печатает все
    четыре исхода, включая нулевые: строка «данных не хватило: 0» — это ответ,
    а её отсутствие человек прочитает как «таких не было», не различив с
    «не проверяли».
    """

    ruleset_version: str
    attempts: tuple[CaseAttempt, ...]

    def by_outcome(self, outcome: CaseOutcome) -> list[CaseAttempt]:
        return [attempt for attempt in self.attempts if attempt.outcome is outcome]

    def as_lines(self) -> list[str]:
        counts = {
            "кейс собран": CaseOutcome.BUILT,
            "кейс не положен по группе": CaseOutcome.NOT_ELIGIBLE,
            "данных не хватило": CaseOutcome.INSUFFICIENT_DATA,
            "вердикта этой версии нет": CaseOutcome.NO_VERDICT,
        }
        lines = [
            f"пороги версии {self.ruleset_version}",
            f"проектов рассмотрено: {len(self.attempts)}",
        ]
        lines.extend(f"{name}: {len(self.by_outcome(outcome))}" for name, outcome in counts.items())
        stale = [attempt for attempt in self.attempts if attempt.stale_subjects]
        if stale:
            # Не исход, а расхождение: печатается, только когда оно есть —
            # иначе строка «0» приучает её не читать.
            lines.append(
                f"вердикт старше купленных данных: {len(stale)} — перезапустите `classify`"
            )
        return lines
