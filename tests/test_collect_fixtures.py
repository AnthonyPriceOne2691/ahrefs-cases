"""Генератор синтетики и fixture-провайдер.

Примеры приёмки: B7 (детерминизм), B8 (дыра — отсутствие месяцев, а не нули),
B11 (пустая история — штатный пропуск).

Эти тесты держат фундамент Ф3: golden-таблица «серия → группа» имеет смысл
только пока серии воспроизводимы.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ahrefs_cases.collect.endpoints import METRICS_HISTORY, REFDOMAINS_HISTORY
from ahrefs_cases.collect.fixtures.generator import SeriesPoint, generate_series
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.fixtures.scenarios import SHAPES, ScenarioName
from ahrefs_cases.collect.fixtures.table import (
    ScenarioTable,
    ScenarioTableError,
    load_table,
)
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.storage._enums import Metric, MetricSource, TargetMode

END = date(2026, 6, 1)
REQUEST = HistoryRequest(
    target="d1.example.com",
    mode=TargetMode.SUBDOMAINS,
    country="US",
    date_from=date(2024, 1, 1),
    date_to=END,
)


def _traffic(points: list[SeriesPoint]) -> list[float]:
    return [point.values[Metric.ORG_TRAFFIC] for point in points]


def test_same_seed_gives_identical_series() -> None:
    """B7: два вызова с одним seed дают одинаковые числа.

    Иначе golden-таблица Ф3 перезаписывалась бы каждым прогоном и перестала бы
    что-либо удерживать — то есть выглядела бы как защита от дрейфа, ею не будучи.
    """
    first = generate_series("d1.example.com", ScenarioName.STEADY_GROWTH, seed=42, end=END)
    second = generate_series("d1.example.com", ScenarioName.STEADY_GROWTH, seed=42, end=END)

    assert [(p.at, p.values) for p in first] == [(p.at, p.values) for p in second]


def test_different_seed_gives_different_series() -> None:
    """B7: обратная сторона — seed действительно влияет.

    Без этой проверки генератор мог бы игнорировать seed, и «детерминизм» был бы
    следствием того, что случайности нет вовсе.
    """
    first = generate_series("d1.example.com", ScenarioName.STEADY_GROWTH, seed=42, end=END)
    second = generate_series("d1.example.com", ScenarioName.STEADY_GROWTH, seed=7, end=END)

    assert _traffic(first) != _traffic(second)


def test_domain_changes_series() -> None:
    """B7: разные домены дают разные уровни, иначе сотня доменов была бы одним."""
    first = generate_series("d1.example.com", ScenarioName.STEADY_GROWTH, seed=42, end=END)
    second = generate_series("d2.example.com", ScenarioName.STEADY_GROWTH, seed=42, end=END)

    assert _traffic(first) != _traffic(second)


def test_data_hole_omits_months_not_zeroes_them() -> None:
    """B8: месяцев дыры в серии нет.

    Ноль означал бы «трафик упал в ноль» — это `poor`, а не `insufficient_data`.
    Разница видна только здесь: дальше по конвейеру обе формы выглядят как числа.
    """
    points = generate_series("hole.example.com", ScenarioName.DATA_HOLE, seed=42, end=END)
    shape = SHAPES[ScenarioName.DATA_HOLE]

    assert len(points) == shape.months - len(shape.holes)
    assert all(value > 0 for value in _traffic(points))


def test_short_history_is_short() -> None:
    """B9: короткая история именно короткая, а не дополненная нулями."""
    points = generate_series("short.example.com", ScenarioName.SHORT_HISTORY, seed=42, end=END)

    assert len(points) == SHAPES[ScenarioName.SHORT_HISTORY].months


def test_late_drop_falls_at_the_end() -> None:
    """B19: провал в конце — рост есть, но последняя точка ниже предпоследних.

    Это ловушка для классификации: по краям периода «А → Б» такой проект
    выглядит успешным, а работы закончились падением.
    """
    traffic = _traffic(generate_series("d5.example.com", ScenarioName.LATE_DROP, seed=42, end=END))

    assert traffic[-1] < max(traffic)
    assert traffic[-1] < traffic[-3]


def test_backlink_spike_moves_refdomains_not_traffic() -> None:
    """B19: скачок ссылочного — refdomains прыгает, трафик нет.

    Сценарий существует ради правила «главная метрика И подтверждающая»: рост
    одних ссылок кейсом не является.
    """
    points = generate_series("d6.example.com", ScenarioName.BACKLINK_SPIKE, seed=42, end=END)
    refdomains = [point.values[Metric.REFDOMAINS] for point in points]
    traffic = _traffic(points)

    assert refdomains[-1] / refdomains[0] > 3.0
    assert traffic[-1] / traffic[0] < 2.0


async def test_fixture_returns_only_requested_metrics() -> None:
    """B10: провайдер отдаёт метрики запрошенного endpoint'а, а не всё подряд."""
    result = await AhrefsFixture().fetch_history(METRICS_HISTORY, REQUEST)

    assert result.source == MetricSource.FIXTURE
    assert set(result.points[0].values) == {Metric.ORG_TRAFFIC}, "E9: шаг 1 просит одно поле"


async def test_fixture_counts_units_by_the_same_model_as_live() -> None:
    """B10: условные units считаются моделью стоимости, а не нулём.

    Ноль был бы проще и вреднее: смета и экран расхода (Ф2б) разрабатывались бы
    на нулях и «заработали» бы только с живым ключом — то есть в Ф7, где чинить
    их дорого.
    """
    metrics = await AhrefsFixture().fetch_history(METRICS_HISTORY, REQUEST)
    refdomains = await AhrefsFixture().fetch_history(REFDOMAINS_HISTORY, REQUEST)

    # Биллинг построчный (замерено в Ф7), поэтому цена зависит от глубины:
    # 18 месяцев по 11 units за строку — 198. Было 378 при двух полях.
    assert metrics.units_actual == METRICS_HISTORY.estimate_units(len(metrics.points))
    assert metrics.units_actual == 198, "E9: 18 строк по 11 units; было 378 при двух полях"
    assert refdomains.units_actual == REFDOMAINS_HISTORY.estimate_units(len(refdomains.points))


async def test_empty_scenario_is_empty_and_free() -> None:
    """B11: у домена без истории ноль точек и ноль units — платить не за что."""
    request = HistoryRequest(
        target="empty.example.com",
        mode=TargetMode.SUBDOMAINS,
        country="US",
        date_from=date(2024, 1, 1),
        date_to=END,
    )

    result = await AhrefsFixture().fetch_history(METRICS_HISTORY, request)

    assert result.is_empty
    assert result.units_actual == 0


async def test_date_from_cuts_the_series() -> None:
    """B6: `date_from` режет историю — на этом будет стоять догруз Ф2б."""
    request = HistoryRequest(
        target="d1.example.com",
        mode=TargetMode.SUBDOMAINS,
        country="US",
        date_from=date(2026, 1, 1),
        date_to=END,
    )

    result = await AhrefsFixture().fetch_history(METRICS_HISTORY, request)

    assert len(result.points) == 6
    assert all(point.at >= date(2026, 1, 1) for point in result.points)


def test_table_assigns_by_name_and_falls_back() -> None:
    """B20: таблица читается из файла проекта, неизвестный домен получает `default`."""
    table = load_table()

    assert table.scenario_for("d47.example.com") is ScenarioName.LATE_DROP
    assert table.scenario_for("EMPTY.example.com") is ScenarioName.EMPTY
    assert table.scenario_for("клиент.рф") is table.default


def test_unknown_scenario_is_an_error_not_a_default(tmp_path: Path) -> None:
    """B20: опечатка в таблице падает, а не откатывается к `steady_growth`.

    Молчаливый откат нарисовал бы всем доменам одну форму, и Ф3 показала бы
    стопроцентное согласие с порогами — самый дорогой сорт зелёного.
    """
    path = tmp_path / "scenarios.yml"
    path.write_text("domains:\n  a.example.com: steady_grwoth\n", encoding="utf-8")

    with pytest.raises(ScenarioTableError, match="steady_grwoth"):
        load_table(path)


def test_missing_table_is_not_a_crash(tmp_path: Path) -> None:
    """B20: нет файла — пустая таблица с дефолтом, сервис работает на чужом списке."""
    table = load_table(tmp_path / "nope.yml")

    assert isinstance(table, ScenarioTable)
    assert table.scenario_for("any.example.com") is table.default
