"""Golden-таблица: сценарий генератора Ф2а → группа. Пример приёмки: D13.

Считается **без базы и без сети**: серия строится генератором, пороги берутся
из сида. Иначе таблица станет медленной и начнёт зависеть от того, что лежит в
дев-окружении (урок L8), а её задача — удерживать смысл порогов между
правками.

Правка сценария в этой поставке — красный флаг. Формы зафиксированы в Ф2а до
того, как появились правила; подгонять данные под пороги значит получить
классификатор, который проходит собственные данные и ошибается на чужих.
"""

from __future__ import annotations

from datetime import date

import pytest

from ahrefs_cases.classify.deltas import between
from ahrefs_cases.classify.points import point_a, point_b
from ahrefs_cases.classify.rules import decide
from ahrefs_cases.classify.series import MetricSeries, max_gap_months, months_covered
from ahrefs_cases.classify.thresholds import Thresholds, load_seed
from ahrefs_cases.collect.fixtures.generator import generate_series
from ahrefs_cases.collect.fixtures.scenarios import ScenarioName
from ahrefs_cases.storage._enums import Group, Metric

PERIOD_END = date(2026, 6, 1)
SEED = 42

EXPECTED: list[tuple[ScenarioName, Group, str]] = [
    (ScenarioName.STEADY_GROWTH, Group.GOOD, "трафик ×2.6 и ссылочное ×1.9 — кейс"),
    (ScenarioName.DECLINE, Group.POOR, "падение на треть"),
    (ScenarioName.SHORT_HISTORY, Group.MEDIUM, "рост есть, но 4 месяца — не «хорошие»"),
    (ScenarioName.DATA_HOLE, Group.INSUFFICIENT_DATA, "дыра в три месяца — серия недостоверна"),
    (ScenarioName.LATE_DROP, Group.POOR, "точка Б ниже точки А на 28 %: провал в конце съел рост"),
    (ScenarioName.BACKLINK_SPIKE, Group.MEDIUM, "ссылочное ×3.4 при трафике +45 %"),
]
"""`weak_growth` в строгой таблице отсутствует намеренно — см. тест ниже:
его группа определяется шумом, и фиксировать её как соответствие значило бы
получить тест, зелёный по случайности."""


def _series(scenario: ScenarioName, domain: str = "d1.example.com") -> MetricSeries:
    points = generate_series(domain, scenario, seed=SEED, end=PERIOD_END)
    series: dict[Metric, dict[date, float]] = {}
    for point in points:
        for metric, value in point.values.items():
            series.setdefault(metric, {})[point.at] = value
    return series


def _decide(series: MetricSeries, thresholds: Thresholds, period_start: date) -> Group:
    a = point_a(series, period_start, thresholds.windows)
    b = point_b(series, PERIOD_END, thresholds.windows)
    months = months_covered(series, Metric.ORG_TRAFFIC)
    after_start = [month for month in months if month >= period_start]
    decision = decide(
        between(a, b),
        b,
        months_after_start=len(after_start),
        max_gap_months=max_gap_months(months),
        thresholds=thresholds,
    )
    return decision.group


def _period_start(series: MetricSeries) -> date:
    """Старт работ — первый месяц серии: сценарии генератора и есть период работ."""
    return months_covered(series, Metric.ORG_TRAFFIC)[0]


@pytest.mark.parametrize(
    ("scenario", "expected", "why"), EXPECTED, ids=[e[0].value for e in EXPECTED]
)
def test_scenario_maps_to_group(scenario: ScenarioName, expected: Group, why: str) -> None:
    """D13: форма серии определяет группу, и это соответствие зафиксировано."""
    series = _series(scenario)
    thresholds = load_seed()

    group = _decide(series, thresholds, _period_start(series))

    assert group is expected, (
        f"{scenario.value}: ожидали {expected.value} ({why}), вышло {group.value}"
    )


def test_weak_growth_sits_on_the_threshold() -> None:
    """Находка, а не соответствие: «слабый рост» балансирует на пороге.

    Форма `weak_growth` (×1.12) при пороге «средних» +10 % и шуме ±3 % даёт
    группу, зависящую от домена: на seed 42 шесть доменов из двенадцати ниже
    порога, шесть выше. Это не дефект правил и не дефект генератора — это
    несогласованность формы и порога, и она **обязана** быть видна, а не
    спрятана в golden-таблице удобным ожиданием.

    Что проверяем: группа лежит между `poor` и `medium` (то есть правила
    работают) и что разброс действительно есть (то есть проблема не исчезла
    сама). Вопрос «каким методом считать рост, чтобы порог ТЗ означал то, что
    задумано» решается калибровкой Ф8 — он записан в спеке.
    """
    thresholds = load_seed()
    groups = set()
    for index in range(12):
        series = _series(ScenarioName.WEAK_GROWTH, f"d{index}.example.com")
        groups.add(_decide(series, thresholds, _period_start(series)))

    assert groups <= {Group.MEDIUM, Group.POOR}
    assert len(groups) == 2, "разброс исчез — форма или порог изменились, проверьте калибровку"


def test_window_averaging_understates_linear_growth() -> None:
    """Усреднение окон систематически занижает линейный рост — на чистых числах.

    Ряд, растущий строго на 12 % за 18 месяцев, по точкам А и Б (среднее по
    два месяца) даёт около 11,3 %. Эффект невелик, но он **односторонний**:
    пороги ТЗ, если они задавались как «последнее к первому», у нас
    срабатывают строже. Знать это надо до калибровки, а не во время неё.
    """
    months = [date(2025, 1 + index, 1) for index in range(12)]
    growing = {
        Metric.ORG_TRAFFIC: {
            month: 1000.0 * (1 + 0.12 * index / (len(months) - 1))
            for index, month in enumerate(months)
        }
    }
    thresholds = load_seed()

    a = point_a(growing, months[0], thresholds.windows)
    b = point_b(growing, months[-1], thresholds.windows)
    pct = between(a, b).metric(Metric.ORG_TRAFFIC)

    assert pct is not None
    assert pct.pct is not None
    assert 10.5 < pct.pct < 11.6, f"ожидали ~11,3 % вместо 12 %, получили {pct.pct:.2f} %"


def test_table_reacts_to_thresholds() -> None:
    """Канарейка: таблица действительно судит по порогам, а не по имени сценария.

    Поднимаем порог «хороших» до недостижимого — `steady_growth` обязан
    перестать быть `good`. Без этой проверки таблица могла бы совпадать по
    случайности и оставаться зелёной при сломанных правилах.
    """
    series = _series(ScenarioName.STEADY_GROWTH)
    thresholds = load_seed()
    strict = thresholds.model_copy(deep=True)
    strict.groups["good"].org_traffic.growth_pct_min = 10_000

    assert _decide(series, thresholds, _period_start(series)) is Group.GOOD
    assert _decide(series, strict, _period_start(series)) is not Group.GOOD


def test_scenarios_are_not_tuned_to_thresholds() -> None:
    """Формы сценариев остались теми, что зафиксированы в Ф2а.

    Тест сторожит соблазн «подогнать» golden-таблицу правкой генератора: если
    множители форм поменяются, это падение, а не тихо обновившийся снимок.
    """
    from ahrefs_cases.collect.fixtures.scenarios import SHAPES

    assert SHAPES[ScenarioName.STEADY_GROWTH].traffic_growth == 2.6
    assert SHAPES[ScenarioName.WEAK_GROWTH].traffic_growth == 1.12
    assert SHAPES[ScenarioName.DECLINE].traffic_growth == 0.68
    assert SHAPES[ScenarioName.BACKLINK_SPIKE].refdomains_growth == 3.4
