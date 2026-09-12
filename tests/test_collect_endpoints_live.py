"""Спеки endpoint'ов против замеров живым ключом 12.09.2026.

Этот файл — не проверка арифметики, а **запись показаний**. Числа и имена
получены живыми запросами узкими окнами; каждое можно перепроверить одной
строкой curl, и в этом его ценность: фикстуры пишем мы сами и согласуем со
своими же догадками, а здесь стоит то, что ответил Ahrefs.

Почему это важнее, чем кажется: обе неверные догадки (`domain_ratings` и
`total-search-volume-history`) читались бы как «у домена нет истории» —
молчаливый пропуск метрики, а не отказ. DR при этом must-have из ТЗ.
"""

from __future__ import annotations

import pytest

from ahrefs_cases.collect.endpoints import ALL_SPECS, MIN_REQUEST_UNITS, EndpointSpec


def spec_by_name(name: str) -> EndpointSpec:
    """Спека по имени. Отсутствие имени — ошибка теста, а не пропуск проверки."""
    for spec in ALL_SPECS:
        if spec.name == name:
            return spec
    message = f"в ALL_SPECS нет endpoint'а {name!r}"
    raise AssertionError(message)


# (endpoint, ключ списка, цена строки) — как ответил живой API 12.09.2026.
MEASURED = [
    ("metrics-history", "metrics", 11),
    ("refdomains-history", "refdomains", 6),
    ("domain-rating-history", "domain_ratings", 2),
    ("pages-history", "pages", 2),
    ("total-search-volume-history", "metrics", 11),
    ("keywords-graph", "keywords", 3),
    ("keywords-history", "keywords", 6),
]


@pytest.mark.parametrize(("name", "list_key", "row_units"), MEASURED)
def test_spec_matches_live_answer(name: str, list_key: str, row_units: int) -> None:
    """Ключ списка и цена строки — те, что пришли с живым ответом."""
    spec = spec_by_name(name)

    assert spec.list_key == list_key
    assert spec.row_units() == row_units


def test_price_is_per_field_not_per_count() -> None:
    """Цена зависит от **того, какие** поля просим, а не от их числа.

    Прежняя модель считала любое поле по 10 и ошибалась в семь раз на ключевых
    словах: пять бакетов стоят 6 units за строку, а не 51.
    """
    keywords = spec_by_name("keywords-history")
    traffic = spec_by_name("metrics-history")

    assert len(keywords.billable_fields()) > len(traffic.billable_fields())
    assert keywords.row_units() < traffic.row_units()


def test_search_volume_reads_its_real_field() -> None:
    """Поле зовётся `total_search_volume`; `search_volume` не пришёл бы никогда."""
    spec = spec_by_name("total-search-volume-history")

    assert "total_search_volume" in spec.metrics
    assert "search_volume" not in spec.metrics


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda spec: spec.name)
def test_minimum_holds_for_every_spec(spec: EndpointSpec) -> None:
    """Запрос дешевле минимума не бывает, и «сколько строк влезает» считается
    от **цены строки**, а не от константы: дешёвые endpoint'ы дают окно шире."""
    assert spec.estimate_units(1) == MIN_REQUEST_UNITS
    assert spec.rows_under_minimum() * spec.row_units() <= MIN_REQUEST_UNITS
    assert (spec.rows_under_minimum() + 1) * spec.row_units() > MIN_REQUEST_UNITS
