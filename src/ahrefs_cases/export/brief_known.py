"""Что сервис знает о пустых пунктах брифа — одно правило на лист PDF и карточку.

Команда агентства 12.10.2026: «много ячеек должен заполнять спец руками —
автоматизация процентов на 60». Часть пунктов сервис знает сам: из входного
файла (ниша, услуга, объём работ, период) и из вердикта (группа, трафик в
точке А). У пустого пункта он подставляет значение с источником в скобках —
копирайтер видит, что это вывод сервиса, а не запись специалиста.

В бриф подстановка не пишется (инвариант 10 `product/brief.md`): форма считала
бы её записью человека, а исправленное правило не дошло бы до записанных брифов.
Она считается заново при каждой сборке листа и чтении карточки — поэтому
«Пересобрать кейсы» печатает её в готовых кейсах без докупки (L41).

Правило одно (`known_for`): лист зовёт его с фактами кейса, карточка — с фактами
проекта и вердикта; вторая копия разошлась бы с первой (Z58, L78). «Не знаю» —
отсутствие подстановки, а не догадка: нет вердикта, услуга «Комплекс», группа
не из кейсовых, ниша без совпадения в словаре типов сайта.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ahrefs_cases.cases.format import number
from ahrefs_cases.cases.model import Period
from ahrefs_cases.storage._enums import Group
from ahrefs_cases.storage.brief import FIELDS, FIELDS_BY_KEY, label_of, service_label

MONTHLY_FROM_MONTHS = 3
"""С какой длины периода услуга — «Ежемесячное продвижение»; короче — «Разовый проект».

Правила команда не дала: три месяца — умолчание агента 13.10.2026 (спека
`brief-autofill`), меняется этой строкой."""


@dataclass(frozen=True, slots=True)
class BriefFacts:
    """Что сервис знает о проекте для подстановки.

    Умолчаний у полей нет: лист и карточка называют каждое (L74) — забытое на
    одной стороне умолчание молча выключило бы там подстановку, и экран с листом
    снова говорили бы о проекте разное (Z58).
    """

    niche: str
    work_volume: int | None
    service: str
    """`service_type` входного файла: `seo`, `linkbuilding`, `pr`, `complex` — или как записали."""

    period: Period
    group: Group | None
    """Группа действующего вердикта; `None` — вердикта нет."""

    traffic_start: float | None
    """Органический трафик в точке А вердикта — число таблицы А → Б; `None` — не знаем."""


Rule = Callable[[BriefFacts, Mapping[str, str]], str]
Words = tuple[tuple[str, re.Pattern[str]], ...]

_DEPARTMENT_SERVICES = frozenset({"seo", "linkbuilding", "pr"})
"""Услуги, у которых отдел одноимённый. Чей «Комплекс», команда не сказала — без подстановки."""

_WEIGHTS: Mapping[Group, tuple[str, str]] = MappingProxyType(
    {Group.GOOD: ("high", "хороший"), Group.MEDIUM: ("medium", "средний")}
)
"""Группа → весомость и группа словами. «Плохому» кейс не собирают, а «нет данных» о
результате не говорит ничего — там весомость решает специалист."""

_OTHER = "other"
"""«Другое» словарь не выбирает: это решение человека, а не вывод по нише."""


def _words(table: str) -> Words:
    """Таблица «пункт — слова через `|`» → поиск. Слово ищется с начала слова ниши,
    короткие («дом», «сад», «еда») — целым словом: иначе «доменные имена» стали бы
    «Домом, садом и ремонтом»."""
    rows = (line.split(maxsplit=1) for line in table.strip().splitlines())
    return tuple((key, re.compile(rf"(?<!\w)(?:{stems.strip()})")) for key, stems in rows)


_TOPIC_WORDS = _words(r"""
fashion        одежд|обув|мод[аеуы]\b|модн|белье\b|сумк|ювелир|бижутер|fashion|cloth|apparel
travel         путешеств|туризм|турист|туроператор|турагент|тур(?:ы|ов|а)?\b|отел|гостиниц|хостел|авиа|курорт|отдых|travel|touris|tours?\b|hotel|flight
health         медиц|здоров|клиник|аптек|фарм|стомат|врач|лечени|больниц|health|medic|clinic|pharm|dental
finance        финанс|банк(?!ет)|кредит|займ|заем|ипотек|страхов|инвест|крипт|форекс|брокер|валют|бухгалт|налог|платеж|financ|fintech|bank|loan|credit|insur|invest|crypto|forex|trading
auto           авто(?!мат|р)|шин(?:ы|а)?\b|шиномонтаж|запчаст|мото|car\b|cars\b|auto\b|automotive|vehicle
pets           зоо|животн|питом|собак|кошк|кошек|ветеринар|корм(?:а|ов|ы)?\b|аквариум|pets?\b|veterinar
beauty         красот|космет|парфюм|макияж|маникюр|барбер|beauty|cosmetic|skincare|makeup|perfum
sport          спорт|фитнес|трениров|тренажер|велосипед|йог[аеиу]\b|sport|fitness|gym\b|yoga
food           ед(?:а|ы|у|ой)\b|питани|продуктов(?:ый|ая|ые|ых)\b|ресторан|кафе\b|кулинар|рецепт|напит|кофе|пицц|суши|food|restaurant|recipe|grocer|cafe\b|coffee
entertainment  игр|развлеч|кино|казино|гемблинг|беттинг|букмекер|музык|концерт|фильм|сериал|аниме|квест|досуг|game|gaming|casino|gambl|betting|movie|music|anime|entertain
education      детск\w* сад|образова|обучени|обучающ|курс|школ|университет|вуз|колледж|репетитор|учеб|тренинг|вебинар|educat|course|school|universit|learning|tutor
hobby          хобби|рукодел|творчеств|рисовани|вязани|шитье|коллекцион|рыбалк|охот|handmade|craft|hobby|fishing|hunting
it             софт|программн|программир|разработ|приложени|хостинг|облачн|кибер|айти|ит\b|it\b|software|saas|devops|hosting|cloud|cyber|tech\b
industry       промышлен|производств|оборудован|станк|станок|завод|металл|спецтехник|industr|manufactur|machinery|equipment
home           дом(?:а|у|ом|е|ов)?\b|ремонт|мебел|стройматериал|строител|стройк|бытов|сад(?:а|у|ом|ы|ов)?\b|садов|огород|дач|интерьер|декор|сантехник|освещени|garden|furniture|interior|renovation|home\b|diy\b
""")
"""Ниша → тематика. Порядок — приоритет: общие слова (оборудование, ремонт, дом) —
в конце, чтобы «ремонт автомобилей» был «Авто», а «спортивное оборудование» — «Спорт».
Модели в сервисе нет: словарь проверяется тестом и правится строкой."""

_SITE_WORDS = _words(r"""
marketplace    маркетплейс|marketplace
classifieds    объявлени|classified
aggregator     агрегатор|сравнени\w* (?:цен|тариф)|aggregator|comparison
ecommerce      магазин|e-?commerce|e-?shop|webshop|shop|stores?\b|retail
saas           saas|сервис(?!н)|платформ|приложени|crm\b|облачн|software|platform|apps?\b|cloud
media          медиа|блог|журнал|новост|сми\b|издани|портал|подкаст|media|blog|news|magazine
directory      справочн|энциклопед|баз[аеуы] знаний|каталог|вики|словар|wiki|directory|knowledge base|encyclop
corporate      корпоратив|визитк|сайт компании|corporate|company website
""")
"""Ниша → тип сайта. Совпадения нет — подстановки нет: тип сайта не выводится из
тематики («финансы» бывают и банком, и блогом)."""


def known_for(facts: BriefFacts, brief: Mapping[str, str]) -> dict[str, str]:
    """Пустой пункт брифа → что сервис подставляет; знать нечего — пункта нет.

    Заполненный специалистом пункт не подменяется: это запись человека. Ключи —
    только из описания брифа (`storage.brief.FIELDS`), а лист печатает каждый его
    пункт (сверяется тестом), поэтому карточка не получит того, чего нет на листе.
    """
    known: dict[str, str] = {}
    for field in FIELDS:
        rule = _RULES.get(field.key)
        if rule is None or brief.get(field.key):
            continue
        value = rule(facts, brief)
        if value:
            known[field.key] = value
    return known


def _label(field_key: str, choice: str) -> str:
    return label_of(FIELDS_BY_KEY[field_key], choice)


def _department(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    service = facts.service.strip().lower()
    if service not in _DEPARTMENT_SERVICES:
        return ""
    return f"{_label('department', service)} (по услуге из файла)"


def _service_kind(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    months = facts.period.months
    kind = "monthly" if months >= MONTHLY_FROM_MONTHS else "one_off"
    return f"{_label('service_kind', kind)} (период {months} мес.)"


def _project_kind(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    """По трафику точки А: был — рост существующего сайта, ноль — запуск нового."""
    traffic = facts.traffic_start
    if traffic is None or traffic < 0:
        return ""
    if traffic == 0:
        return f"{_label('project_kind', 'launch')} (на старте трафика не было)"
    return f"{_label('project_kind', 'growth')} (трафик на старте — {number(traffic)})"


def _topic(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    """Тематика по нише; ниша без совпадения — сама ниша: файл её знает, словарь — нет."""
    niche = facts.niche.strip()
    if not niche:
        return ""
    topic = _pick(niche, "topic", _TOPIC_WORDS)
    if not topic:
        return f"{niche} (ниша из файла)"
    return f"{_label('topic', topic)} (по нише «{niche}»)"


def _site_type(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    niche = facts.niche.strip()
    site_type = _pick(niche, "site_type", _SITE_WORDS) if niche else ""
    return f"{_label('site_type', site_type)} (по нише «{niche}»)" if site_type else ""


def _budget(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    if facts.work_volume is None:
        return ""
    return f"{number(float(facts.work_volume))} (объём работ из файла)"


def _dynamics_slice(_facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    return f"{_label('dynamics_slice', 'whole')} (по умолчанию)"


def _first_period(facts: BriefFacts, brief: Mapping[str, str]) -> str:
    """Период 1 — весь период с услугой, пока срез «весь»; «по этапам» делит специалист."""
    if brief.get("dynamics_slice", "") not in ("", "whole"):
        return ""
    start, end = facts.period.start, facts.period.end
    period = f"{start:%m.%Y} — {end:%m.%Y}"
    return f"{period}: {service_label(facts.service)} (период и услуга из файла)"


def _result_weight(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    found = _WEIGHTS.get(facts.group) if facts.group is not None else None
    if found is None:
        return ""
    weight, group = found
    return f"{_label('result_weight', weight)} (группа «{group}»)"


def _pick(niche: str, field_key: str, words: Words) -> str:
    """Пункт списка по нише: сперва ключ или подпись целиком, затем слова словаря по порядку."""
    plain = _plain(niche)
    for choice in FIELDS_BY_KEY[field_key].choices:
        if choice.key != _OTHER and plain in (_plain(choice.key), _plain(choice.label)):
            return choice.key
    return next((key for key, pattern in words if pattern.search(plain)), "")


def _plain(text: str) -> str:
    """Для сравнения: без регистра, «ё» как «е» — в нише его пишут то так, то так."""
    return text.strip().casefold().replace("ё", "е")


_RULES: Mapping[str, Rule] = MappingProxyType(
    {
        "department": _department,
        "service_kind": _service_kind,
        "project_kind": _project_kind,
        "site_type": _site_type,
        "topic": _topic,
        "budget": _budget,
        "dynamics_slice": _dynamics_slice,
        "case_period_1": _first_period,
        "result_weight": _result_weight,
    }
)
"""Пункт брифа → откуда сервис его знает. Пункта нет — его знает только специалист."""
