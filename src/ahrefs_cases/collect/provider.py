"""Интерфейс доступа к Ahrefs и типы его ответа.

Единственная точка, через которую сбор узнаёт историю домена. Реализаций две —
`AhrefsFixture` (разработка, тесты, ноль units) и `AhrefsLive` (появится ключ).
Выбор делает конфиг, не код: `AHREFS_PROVIDER=fixture|live`.

Почему `Protocol`, а не базовый класс: fixture и live не разделяют ни строчки
реализации — у одного генератор, у другого HTTP. Общий предок склеил бы их
только формально, зато потребовал бы наследования там, где нужен лишь контракт.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.storage._enums import Metric, MetricSource, TargetMode


@dataclass(frozen=True, slots=True)
class HistoryRequest:
    """Что спрашиваем. `date_from` — точка инкрементального догруза (Ф2б).

    `country` из файла проекта, а не константа: гео-разрез задаёт агентство, и
    «US по умолчанию» тихо исказил бы кейс немецкого клиента.
    """

    target: str
    mode: TargetMode
    country: str
    date_from: date
    date_to: date | None = None


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """Точка серии: месяц и значения метрик в нём."""

    at: date
    values: Mapping[Metric, float]


@dataclass(frozen=True, slots=True)
class HistoryResult:
    """Ответ провайдера вместе с ценой.

    Цена возвращается **с данными**, а не считается вызывающим: у live она
    приходит заголовком ответа и является фактом, у fixture — расчётом по той же
    модели. Считай её снаружи — и журнал units показывал бы оценку в обоих
    случаях, то есть перестал бы отличать факт от прогноза.
    """

    endpoint: str
    target: str
    points: tuple[HistoryPoint, ...]
    units_estimated: int
    units_actual: int
    source: MetricSource

    @property
    def is_empty(self) -> bool:
        """Пустая история — штатный случай (молодой домен), не ошибка.

        Такой проект пропускается с пометкой `no_data`, и прогон продолжается:
        останавливать сотню доменов из-за одного — то же, что не собрать ничего.
        """
        return not self.points


class AhrefsProvider(Protocol):
    """Контракт обоих провайдеров."""

    source: MetricSource
    """Чем помечать точки в базе. `fixture` и `live` не смешиваются в одной серии:
    иначе непонятно, за какие данные заплачено."""

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        """История по одному endpoint'у и одному домену."""
        ...


def points_to_rows(result: HistoryResult) -> list[tuple[date, Metric, float]]:
    """Ответ → плоские строки под `MetricPoint`.

    Разворачивание живёт здесь, а не в записи в базу: у обоих провайдеров форма
    ответа одна, и повторять её разбор в `series.py` значило бы иметь два места,
    где `None` в значении превращается в ноль.
    """
    return [
        (point.at, metric, value)
        for point in result.points
        for metric, value in point.values.items()
    ]
