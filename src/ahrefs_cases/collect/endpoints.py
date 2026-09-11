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
"""Каждое биллингуемое поле. `date` не считается: это ось, не метрика.
Замерено: `x-api-units-cost-row` = 21 при двух полях, 11 при одном."""

ROW_UNITS = 1
"""Надбавка за саму строку поверх полей. Из тех же замеров: 10×2+1 = 21."""

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

    needs_series: bool = False
    """Данные нужны **серией**, а не двумя точками, и цена этого не решает.

    Ступень кейса покупает кривую позиций именно ради кривой: две точки дешевле
    (100 units против 399), но показать по ним нечего. Там, где назначение
    данных известно заранее, выбирать схему по цене — значит купить дешёвое и
    ненужное. Вердикту, наоборот, серия не нужна, и там решает цена.
    """

    flat_cost: int | None = None
    """Цена строки, если документация называет её отдельно
    (`refdomains-history` — 5). Замером **не подтверждена**: разведка Ф7
    трогала только `metrics-history`. Трактуем как цену строки, а не запроса —
    это дороже и потому безопаснее для сметы: занизить цену хуже, чем завысить."""

    def billable_fields(self) -> tuple[str, ...]:
        return tuple(field for field in self.select if field != _DATE_FIELD)

    def row_units(self) -> int:
        """Цена одной строки ответа.

        Замерено живым ключом 10.09.2026: `x-api-units-cost-row` = 21 при двух
        полях и 11 при одном, то есть «10 за каждое биллингуемое поле плюс 1 за
        саму строку». Совпадает на обоих замерах.
        """
        if self.flat_cost is not None:
            return self.flat_cost
        return FIELD_UNITS * len(self.billable_fields()) + ROW_UNITS

    def rows_under_minimum(self) -> int:
        """Сколько строк влезает в минимальную стоимость запроса.

        Минимум в 50 units — не только ограничение, но и **неиспользованная
        ёмкость**: при одном поле строка стоит 11, значит четыре строки (44)
        стоят столько же, сколько одна, а пятая (55) минимум пробивает.

        Живёт здесь, а не константой в планировщике, потому что это следствие
        замеренной цены строки, а не свойство мира: при двух полях под минимум
        влезает уже две строки. Константа 4 в планировщике разошлась бы с
        моделью при первой правке `select` — и разошлась бы молча, потому что
        цена осталась бы верной, а окно перестало бы быть бесплатным.
        """
        return max(1, MIN_REQUEST_UNITS // self.row_units())

    def estimate_units(self, rows: int = 1) -> int:
        """Стоимость запроса, возвращающего `rows` строк.

        **Биллинг построчный** — это главное открытие разведки Ф7. Прежняя
        модель («50 за запрос») занижала смету в девять раз: запрос за 21 месяц
        стоит 441 unit, а не 50, и preflight пропускал бы прогон, съедающий
        квоту на четверти списка.

        Минимум в 50 units существует и проверен: запрос на одну строку стоил
        50 при расчётной цене 21.
        """
        return max(MIN_REQUEST_UNITS, self.row_units() * max(1, rows))


METRICS_HISTORY = EndpointSpec(
    name="metrics-history",
    path="/v3/site-explorer/metrics-history",
    select=("date", "org_traffic"),
    list_key="metrics",
    metrics=MappingProxyType({"org_traffic": Metric.ORG_TRAFFIC}),
    stage=1,
)
"""Шаг 1 воронки: единственный endpoint, который платится за все 100 проектов.

Поле **одно**. `org_cost` уехал отсюда после замера цены: второе биллингуемое
поле удваивает цену строки (21 против 11), а читателя у него нет — ни в
правилах Ф3, ни в блоках кейса по ТЗ. Вернётся ступенью графика в Ф4, где
стоимость трафика показывают вместе с самим графиком и только тем проектам, у
которых будет кейс. `paid_traffic` и `paid_cost` не просим никогда."""

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
    stage=3,
)
"""DR — must-have из списка ТЗ, и в кейсе это **число**, а не кривая.

Стоял под флагом на шаге 2 и был выключен: группу он не определяет, а тридцати
кандидатам обошёлся бы в 3000 units. Переехал в ступень кейса 11.09.2026 — там
он покупается двумя точками десяти проектам и стоит 1000. Так требование ТЗ
выполняется, а не откладывается: «DR вырос с 12 до 34» — одна из самых
узнаваемых строк SEO-кейса.

Флага у него больше нет: настройка, которая выключает требование ТЗ, — это
способ забыть о нём молча (урок L33)."""

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

KEYWORDS_GRAPH = EndpointSpec(
    name="keywords-graph",
    path="/v3/site-explorer/keywords-history",
    select=("date", "top3", "top4_10"),
    list_key="keywords",
    metrics=MappingProxyType({"top3": Metric.KW_TOP3, "top4_10": Metric.KW_TOP4_10}),
    stage=3,
    needs_series=True,
)
"""Кривая позиций для кейса: **две корзины вместо пяти**.

Тот же endpoint, что у шага 2, и отличается только `select` — но этого хватает,
чтобы цена строки упала с 51 до 21. Графику нужны топ-3 и топ-10: это то, что
читается как «вывели в топ». Остальные три корзины живут в кейсе числами на
границах периода, а границы куплены шагом 2 — платить за их середину значит
платить за числа, которых в кейсе нет.

Разрешение месячное: ТЗ называет гранулярность прямо, и после сужения полей
квартальная экономила бы 105 units на кейс — дешевле информативности."""

METRICS_VALUE = EndpointSpec(
    name="metrics-value",
    path="/v3/site-explorer/metrics-history",
    select=("date", "org_cost"),
    list_key="metrics",
    metrics=MappingProxyType({"org_cost": Metric.ORG_COST}),
    stage=3,
)
"""`traffic value` для кейса — число, а не кривая.

Из must-have списка ТЗ. С шага 1 убран потому, что второе поле удваивало цену
строки **всем ста доменам**; здесь покупается двум точкам десяти кейсов и стоит
100 units против 209 за серию, которую никто не показывает."""

ALL_SPECS: tuple[EndpointSpec, ...] = (
    METRICS_HISTORY,
    KEYWORDS_HISTORY,
    REFDOMAINS_HISTORY,
    DOMAIN_RATING_HISTORY,
    PAGES_HISTORY,
    TOTAL_SEARCH_VOLUME_HISTORY,
    KEYWORDS_GRAPH,
    METRICS_VALUE,
)

STAGE1_SPECS: tuple[EndpointSpec, ...] = tuple(spec for spec in ALL_SPECS if spec.stage == 1)
STAGE2_SPECS: tuple[EndpointSpec, ...] = tuple(spec for spec in ALL_SPECS if spec.stage == 2)
STAGE3_SPECS: tuple[EndpointSpec, ...] = tuple(spec for spec in ALL_SPECS if spec.stage == 3)
"""Ступень кейса: докупается только тем, у кого кейс будет."""
