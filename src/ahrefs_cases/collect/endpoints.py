"""Спеки history-endpoint'ов Ahrefs: различия данными, а не кодом.

Шесть endpoint'ов отличаются именем, набором `select`, ключом списка в ответе и
ценой. Разложи это ветками — и седьмой endpoint означал бы правку транспорта,
воронки и сметы; здесь он означает запись в таблице.

Модель стоимости живёт **здесь же**, в одном месте на оба провайдера: fixture
считает по ней условные units, live в Ф7 сверит с заголовками
`x-api-units-cost-*`. Расхождение станет наблюдаемой величиной, а не сюрпризом в
середине платного прогона.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping  # noqa: UP035 — MappingProxyType требует typing-формы в аннотации поля

from ahrefs_cases.storage._enums import Metric

MIN_REQUEST_UNITS = 50
"""Минимальная стоимость запроса по документации Ahrefs (docs/RESEARCH_AHREFS_API.md)."""

FIELD_UNITS = 10
"""Каждое биллингуемое поле `metrics-history`. `date` не считается: это ось, не метрика."""

_DATE_FIELD = "date"


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    """Один history-endpoint: что просим, как читаем ответ, сколько это стоит."""

    name: str
    path: str
    select: tuple[str, ...]
    list_key: str
    """Ключ списка в теле ответа. У Ahrefs он свой у каждого endpoint'а."""

    metrics: Mapping[str, Metric]
    """Поле ответа → метрика домена. Имена API и имена в базе разошлись сознательно:
    `top3` в API против `kw_top3` в базе, иначе метрики ключевых слов и метрики
    страниц смешались бы в одном пространстве имён."""

    stage: int
    """Ступень воронки: 1 — всем проектам, 2 — только кандидатам в кейсы."""

    flat_cost: int | None = None
    """Фиксированная цена запроса, если она документирована отдельно
    (`refdomains-history` — 5 units). `None` — цена считается по полям."""

    def billable_fields(self) -> tuple[str, ...]:
        return tuple(field for field in self.select if field != _DATE_FIELD)

    def estimate_units(self) -> int:
        """Оценка стоимости одного запроса.

        Гипотеза, а не факт: документация Ahrefs называет и минимум в 50 units, и
        отдельную цену `refdomains-history` в 5, не объясняя, как они сочетаются.
        Принято, что фиксированная цена **заменяет** минимум. Ф7 сверит с
        заголовком ответа и поправит здесь одну строку, а не шесть мест.
        """
        if self.flat_cost is not None:
            return self.flat_cost
        return max(MIN_REQUEST_UNITS, FIELD_UNITS * len(self.billable_fields()))


METRICS_HISTORY = EndpointSpec(
    name="metrics-history",
    path="/v3/site-explorer/metrics-history",
    select=("date", "org_traffic", "org_cost"),
    list_key="metrics",
    metrics=MappingProxyType({"org_traffic": Metric.ORG_TRAFFIC, "org_cost": Metric.ORG_COST}),
    stage=1,
)
"""Шаг 1 воронки: единственный endpoint, который платится за все 100 проектов.
`paid_traffic` и `paid_cost` не просим никогда — это +20 units на запрос за
данные, которых нет в кейсе."""

KEYWORDS_HISTORY = EndpointSpec(
    name="keywords-history",
    path="/v3/site-explorer/keywords-history",
    select=("date", "top3", "top4_10", "top11_20", "top21_50", "top51_plus"),
    list_key="keywords",
    metrics=MappingProxyType(
        {
            "top3": Metric.KW_TOP3,
            "top4_10": Metric.KW_TOP4_10,
            "top11_20": Metric.KW_TOP11_20,
            "top21_50": Metric.KW_TOP21_50,
            "top51_plus": Metric.KW_TOP51_PLUS,
        }
    ),
    stage=2,
)

REFDOMAINS_HISTORY = EndpointSpec(
    name="refdomains-history",
    path="/v3/site-explorer/refdomains-history",
    select=("date", "refdomains"),
    list_key="refdomains",
    metrics=MappingProxyType({"refdomains": Metric.REFDOMAINS}),
    stage=2,
    flat_cost=5,
)

DOMAIN_RATING_HISTORY = EndpointSpec(
    name="domain-rating-history",
    path="/v3/site-explorer/domain-rating-history",
    select=("date", "domain_rating"),
    list_key="domain_rating",
    metrics=MappingProxyType({"domain_rating": Metric.DR}),
    stage=2,
)
"""Под флагом `AHREFS_COLLECT_DR_HISTORY`: DR приятно показать в кейсе, но группу
он не определяет, а стоит как полноценный запрос."""

PAGES_HISTORY = EndpointSpec(
    name="pages-history",
    path="/v3/site-explorer/pages-history",
    select=("date", "pages"),
    list_key="pages",
    metrics=MappingProxyType({"pages": Metric.PAGES}),
    stage=2,
)

TOTAL_SEARCH_VOLUME_HISTORY = EndpointSpec(
    name="total-search-volume-history",
    path="/v3/site-explorer/total-search-volume-history",
    select=("date", "search_volume"),
    list_key="search_volume",
    metrics=MappingProxyType({"search_volume": Metric.SEARCH_VOLUME}),
    stage=2,
)

ALL_SPECS: tuple[EndpointSpec, ...] = (
    METRICS_HISTORY,
    KEYWORDS_HISTORY,
    REFDOMAINS_HISTORY,
    DOMAIN_RATING_HISTORY,
    PAGES_HISTORY,
    TOTAL_SEARCH_VOLUME_HISTORY,
)

STAGE1_SPECS: tuple[EndpointSpec, ...] = tuple(spec for spec in ALL_SPECS if spec.stage == 1)
STAGE2_SPECS: tuple[EndpointSpec, ...] = tuple(spec for spec in ALL_SPECS if spec.stage == 2)
