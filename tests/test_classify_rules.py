"""Границы правил классификации на числах, а не на сценариях.

Примеры приёмки: D1 (выброс на границе), D3, D5 (порог месяцев понижает
группу), D6 (мало данных ≠ плохо), D7 и D8 («главная И подтверждающая»),
D9 (дыра), D10 (форма объяснения), D11 (сортировка по абсолюту).

Вход подаётся числами: сценарии проверяют формы целиком, а здесь проверяется
именно порог — где ошибка стоит группы.
"""

from __future__ import annotations

from datetime import date

import pytest

from ahrefs_cases.classify.deltas import between
from ahrefs_cases.classify.points import point_a, point_b
from ahrefs_cases.classify.rules import Decision, decide
from ahrefs_cases.classify.series import MetricSeries, max_gap_months, months_covered
from ahrefs_cases.classify.thresholds import Thresholds, load_seed
from ahrefs_cases.storage._enums import Group, Metric

START = date(2025, 1, 1)


def _months(count: int, *, start: date = START) -> list[date]:
    return [
        date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1)
        for i in range(count)
    ]


def _series(
    traffic: list[float],
    *,
    refdomains: list[float] | None = None,
    top3: list[float] | None = None,
    top4_10: list[float] | None = None,
    start: date = START,
    skip: set[int] | None = None,
) -> MetricSeries:
    """Серия из явных чисел. `skip` выбрасывает месяцы — это дыра, а не нули."""
    months = _months(len(traffic), start=start)
    omitted = skip or set()
    series: dict[Metric, dict[date, float]] = {Metric.ORG_TRAFFIC: {}}
    for index, month in enumerate(months):
        if index in omitted:
            continue
        series[Metric.ORG_TRAFFIC][month] = traffic[index]
        for metric, values in (
            (Metric.REFDOMAINS, refdomains),
            (Metric.KW_TOP3, top3),
            (Metric.KW_TOP4_10, top4_10),
        ):
            if values is not None:
                series.setdefault(metric, {})[month] = values[index]
    return series


def _decide(series: MetricSeries, thresholds: Thresholds | None = None) -> Decision:
    rules = thresholds or load_seed()
    months = months_covered(series, Metric.ORG_TRAFFIC)
    a = point_a(series, months[0], rules.windows)
    b = point_b(series, months[-1], rules.windows)
    return decide(
        between(a, b),
        b,
        months_after_start=len(months),
        max_gap_months=max_gap_months(months),
        thresholds=rules,
    )


def _ramp(start: float, end: float, count: int) -> list[float]:
    step = (end - start) / (count - 1)
    return [start + step * index for index in range(count)]


def test_window_halves_the_outlier_but_does_not_erase_it() -> None:
    """D1: окно **смягчает** выброс вдвое — и это всё, что оно делает.

    Ожидание «группа не изменится» оказалось неверным, и это нашёл тест.
    На плоской серии единственный月 с удвоением даёт по last-точке +100 %, а
    по окну в два месяца — +50 %: влияние ровно вдвое меньше, но порог
    «средних» всё равно пройден.

    Вывод, который надо знать до калибровки: усреднение по двум месяцам не
    защищает от одиночного выброса, а лишь делит его пополам. Настоящая
    устойчивость — окно от трёх месяцев или медиана вместо среднего; и то и
    другое меняет смысл порогов ТЗ, поэтому решается с заказчиком в Ф8, а не
    здесь.
    """
    flat = [1000.0] * 12
    spiked = [*flat[:-1], 2000.0]
    thresholds = load_seed()

    months = months_covered(_series(spiked), Metric.ORG_TRAFFIC)
    a = point_a(_series(spiked), months[0], thresholds.windows)
    b = point_b(_series(spiked), months[-1], thresholds.windows)
    windowed = between(a, b).metric(Metric.ORG_TRAFFIC)

    assert windowed is not None
    assert windowed.pct == pytest.approx(50.0), "окно обязано делить выброс пополам"
    assert _decide(_series(flat)).group is Group.POOR
    assert _decide(_series(spiked)).group is Group.MEDIUM, "ограничение метода, а не сюрприз"


@pytest.mark.parametrize(
    ("window", "expected_pct"), [(2, 50.0), (3, 100 / 3), (4, 25.0), (6, 100 / 6)]
)
def test_no_practical_window_saves_from_a_single_outlier(window: int, expected_pct: float) -> None:
    """D1: расширение окна не спасает — порог «средних» слишком низок для этого.

    Один аномальный месяц из двенадцати на плоской серии даёт +50 % при окне
    в два месяца и всё ещё +16,7 % при окне в шесть — то есть выше порога
    «средних» уровня +10 % (порог заказчика) при **любом** практичном окне.
    Порог в тесте задаётся явно, потому что умолчания репозитория нейтральные,
    а разговор с заказчиком идёт про его числа. Чтобы выброс перестал
    делать плоский проект «средним», нужно окно от десяти месяцев, а это уже
    не «окно у границы периода», а усреднение всего периода.

    Настоящее лекарство — медиана вместо среднего (медиана двенадцати месяцев
    с одним выбросом равна 1000, рост 0 %). Это смена метода, заданного ТЗ,
    поэтому решается с заказчиком при калибровке Ф8. Тест фиксирует цифры,
    чтобы разговор шёл на них.
    """
    spiked = _series([*[1000.0] * 11, 2000.0])
    thresholds = load_seed().model_copy(deep=True)
    thresholds.groups["medium"].org_traffic.growth_pct_min = 10.0
    thresholds.windows.point_a_months = window
    thresholds.windows.point_b_months = window

    months = months_covered(spiked, Metric.ORG_TRAFFIC)
    a = point_a(spiked, months[0], thresholds.windows)
    b = point_b(spiked, months[-1], thresholds.windows)
    delta = between(a, b).metric(Metric.ORG_TRAFFIC)

    assert delta is not None
    assert delta.pct == pytest.approx(expected_pct, abs=0.1)
    assert _decide(spiked, thresholds).group is Group.MEDIUM


def test_medium_band() -> None:
    """D3: рост внутри вилки даёт «средних».

    Вход считается **от порога**, а не задан числом: умолчания репозитория
    нейтральные (пороги заказчика в git не уезжают), и тест, прибитый к
    конкретным процентам, ломался бы при каждой смене умолчаний, ничего при
    этом не проверяя.
    """
    thresholds = load_seed()
    inside = thresholds.medium.org_traffic.growth_pct_min * 1.5

    decision = _decide(_series(_ramp(1000, 1000 * (1 + inside / 100), 12)))

    assert decision.group is Group.MEDIUM


def test_months_lower_the_group_not_reject_the_project() -> None:
    """D5: четыре месяца при требовании «хороших» в шесть — это `medium`.

    Порог месяцев отсекает **группу**, а не проект: у него есть рост и есть
    данные, просто на «хорошие» их пока не хватает.
    """
    series = _series(
        _ramp(1000, 1800, 4),
        refdomains=_ramp(100, 200, 4),
        top3=_ramp(10, 30, 4),
        top4_10=_ramp(20, 60, 4),
    )

    decision = _decide(series)

    assert decision.group is Group.MEDIUM


def test_two_months_is_insufficient_not_poor() -> None:
    """D6: «нет данных» и «плохой результат» — разные группы.

    Они ведут к разным действиям: докупить историю против не делать кейс.
    Слить их значило бы потерять проекты, у которых просто мало месяцев.
    """
    decision = _decide(_series(_ramp(1000, 2000, 2)))

    assert decision.group is Group.INSUFFICIENT_DATA
    assert any(reason.subject == "months_after_start" for reason in decision.reasons)


def test_main_metric_without_supporting_is_not_good() -> None:
    """D7: трафик вырос сильно, подтверждающих нет — не «хорошие».

    В «хорошие» ТЗ пускает только при главной метрике И минимум одной
    подтверждающей. `medium` при этом остаётся достижимым — иначе такой проект
    не попал бы никуда (конфликт порогов, описан в спеке).
    """
    series = _series(
        _ramp(1000, 6000, 12),
        refdomains=_ramp(100, 102, 12),
        top3=_ramp(10, 10, 12),
        top4_10=_ramp(20, 21, 12),
    )

    decision = _decide(series)

    assert decision.group is Group.MEDIUM
    supporting = next(r for r in decision.reasons if r.subject == "good.supporting_required")
    assert supporting.passed is False


def test_supporting_without_main_metric_is_not_good() -> None:
    """D8: ссылочное ×3.4 при трафике +45 % — не «хорошие».

    Рост одних ссылок кейсом не является: главная метрика та, ради которой
    клиент платил.
    """
    series = _series(
        _ramp(1000, 1450, 12),
        refdomains=_ramp(100, 340, 12),
        top3=_ramp(10, 25, 12),
        top4_10=_ramp(20, 50, 12),
    )

    decision = _decide(series)

    assert decision.group is Group.MEDIUM
    traffic_pct = next(r for r in decision.reasons if r.subject == "good.org_traffic_pct")
    assert traffic_pct.passed is False


def test_long_gap_makes_series_untrustworthy() -> None:
    """D9: дыра длиннее допустимой — `insufficient_data`, а не расчёт по огрызкам."""
    series = _series(_ramp(1000, 3000, 12), skip={4, 5, 6})

    decision = _decide(series)

    assert decision.group is Group.INSUFFICIENT_DATA
    gap = next(r for r in decision.reasons if r.subject == "series_gap_months")
    assert gap.fact == 3


def test_reasons_carry_fact_threshold_and_verdict() -> None:
    """D10: по каждому условию видно значение, порог и сработало ли оно.

    По этим записям человек воспроизводит решение, не читая код, — и именно
    они показываются на экране Ф6.
    """
    decision = _decide(_series(_ramp(1000, 3000, 12), refdomains=_ramp(100, 200, 12)))

    assert decision.reasons
    for reason in decision.reasons:
        assert reason.subject
        assert isinstance(reason.passed, bool)
        assert reason.note
    payload = decision.reasons_json()
    assert {"subject", "fact", "threshold", "passed", "note", "decisive"} <= set(payload[0])


def test_sort_key_is_absolute_growth() -> None:
    """D11: внутри группы первым идёт больший абсолютный прирост.

    Так закрыто расхождение ответов заказчика: вопрос 28 задаёт порог в
    процентах, вопрос 30 требует приоритета большему абсолютному числу.
    """
    big_absolute = _decide(_series(_ramp(10_000, 16_000, 12)))
    big_percent = _decide(_series(_ramp(400, 1600, 12)))

    ranked = sorted([big_percent, big_absolute], key=lambda d: d.sort_key, reverse=True)

    assert ranked[0] is big_absolute


def test_score_does_not_decide_the_group() -> None:
    """D16: `score` сортирует внутри группы, но не подменяет пороги.

    Иначе сумма весов начала бы решать за пороги, которые утверждает заказчик,
    и «почему тут good» перестало бы отвечаться порогами вовсе.
    """
    thresholds = load_seed()
    heavy = thresholds.model_copy(deep=True)
    heavy.score.weights.org_traffic_growth_abs = 1000.0

    series = _series(_ramp(1000, 1120, 12))

    assert _decide(series, thresholds).group is _decide(series, heavy).group


@pytest.mark.parametrize("growth", [0.68, 0.9, 1.0])
def test_no_growth_is_poor(growth: float) -> None:
    """D4: падение и рост меньше +10 % — «плохие», кейс не формируется."""
    decision = _decide(_series(_ramp(1000, 1000 * growth, 12)))

    assert decision.group is Group.POOR


def test_growth_from_zero_does_not_crash() -> None:
    """D17: рост с нуля не даёт бесконечности и не роняет расчёт.

    Относительная дельта от нулевой базы не определена; правила обязаны
    решать такой случай явно, а не делить на ноль.
    """
    series = _series([0.0, 0.0, 100.0, 200.0, 300.0, 400.0])

    decision = _decide(series)

    assert decision.group in {Group.POOR, Group.MEDIUM, Group.INSUFFICIENT_DATA}
