"""Что сервис знает о пустых пунктах брифа — одно правило на лист PDF и карточку.

Команда агентства 12.10.2026: «много ячеек должен заполнять спец руками —
автоматизация процентов на 60». Часть пунктов сервис знает сам: из входного
файла (ниша, услуга, объём работ, период, кто вёл), из вердикта (группа,
трафик и Domain Rating в точках А и Б), из купленной динамики (месячный ряд
трафика) и из базы (другие проекты того же домена) — владелец 13.10.2026:
«добавляй ещё пункты, которые прям сейчас можем заполнить». У пустого пункта
сервис подставляет значение с источником в скобках — копирайтер видит, что это
вывод сервиса, а не запись специалиста.

В бриф подстановка не пишется (инвариант 10 `product/brief.md`): форма считала
бы её записью человека, а исправленное правило не дошло бы до записанных брифов.
Она считается заново при каждой сборке листа и чтении карточки — поэтому
«Пересобрать кейсы» печатает её в готовых кейсах без докупки (L41).

Правило одно (`known_for`): лист зовёт его с фактами кейса, карточка — с фактами
проекта и вердикта; вторая копия разошлась бы с первой (Z58, L78). «Не знаю» —
отсутствие подстановки, а не догадка: нет вердикта, услуга «Комплекс», группа
не из кейсовых, ниша без совпадения в словаре типов сайта, в файле не сказано,
кто вёл, в цифрах нет просадок, у домена нет второго проекта.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from types import MappingProxyType

from ahrefs_cases.cases.format import number, percent
from ahrefs_cases.cases.model import ParallelService, Period
from ahrefs_cases.storage._enums import Group
from ahrefs_cases.storage.brief import FIELDS, FIELDS_BY_KEY, label_of, service_label

MONTHLY_FROM_MONTHS = 3
"""С какой длины периода услуга — «Ежемесячное продвижение»; короче — «Разовый проект».

Правила команда не дала: три месяца — умолчание агента 13.10.2026 (спека
`brief-autofill`), меняется этой строкой."""

DROP_SHARE = 0.15
"""С какой просадки органического трафика к прошлому месяцу сервис называет её в
«Трудностях». Оценка Ahrefs гуляет на 5–10 % от месяца к месяцу — меньшая просадка
была бы шумом. Умолчание агента 13.10.2026 (спека `brief-known-more`), меняется
этой строкой."""

RATING_DROP = 3.0
"""На сколько пунктов Domain Rating должен упасть от точки А к Б, чтобы попасть в
«Трудности»: на пункт-два он ходит без всякой причины. Умолчание агента 13.10.2026."""

MAX_DROPS = 3
"""Больше трёх просадок подсказка не называет — самые глубокие: длинный список
читается как отчёт, а не как вопрос специалисту."""


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

    owner: str
    """«Кто вёл проект» из входного файла; пусто — не знаем."""

    traffic: tuple[tuple[date, float], ...]
    """Месячный ряд органического трафика — тот, по которому собран кейс, только
    измеренные месяцы; пусто — ряда нет."""

    rating: tuple[float, float] | None
    """Domain Rating в точках А и Б вердикта — числа таблицы А → Б; `None` — в таблице его нет."""

    parallel: tuple[ParallelService, ...]
    """Проекты того же домена с другой услугой в пересекающийся период (`cases.parallel`)."""


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

_YMYL = frozenset({"finance", "health"})
"""Тематики, где Google строже к экспертности и доверию (Your Money or Your Life) —
«Особенность проекта», которую копирайтер иначе не узнает из цифр."""


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
finance        финанс|финтех|банк(?!ет)|кредит|займ|заем|ипотек|страхов|инвест|крипт|форекс|брокер|валют|бухгалт|налог|платеж|financ|fintech|bank|loan|credit|insur|invest|crypto|forex|trading
auto           авто(?!мат|р)|шин(?:ы|а)?\b|шиномонтаж|запчаст|мото|car\b|cars\b|auto\b|automotive|vehicle
pets           зоо|животн|питом|собак|кошк|кошек|ветеринар|корм(?:а|ов|ы)?\b|аквариум|pets?\b|veterinar
beauty         красот|космет|парфюм|макияж|маникюр|барбер|beauty|cosmetic|skincare|makeup|perfum
sport          спорт|фитнес|трениров|тренажер|велосипед|йог[аеиу]\b|sport|fitness|gym\b|yoga
food           ед(?:а|ы|у|ой)\b|питани|продуктов(?:ый|ая|ые|ых)\b|ресторан|кафе\b|кулинар|рецепт|напит|кофе|пицц|суши|food|restaurant|recipe|grocer|cafe\b|coffee
entertainment  игр|развлеч|кино|казино|гемблинг|беттинг|букмекер|музык|концерт|фильм|сериал|аниме|квест|досуг|game|gaming|casino|gambl|betting|movie|music|anime|entertain
education      детск\w* сад|образова|обучени|обучающ|курс|школ|университет|вуз|колледж|репетитор|учеб|тренинг|вебинар|educat|course|school|universit|learning|tutor
hobby          хобби|рукодел|творчеств|рисовани|вязани|шитье|коллекцион|рыбалк|охот|handmade|craft|hobby|fishing|hunting
it             ^по$|софт|программн|программир|разработ|автоматизац|приложени|хостинг|облачн|кибер|айти|ит\b|it\b|software|saas|devops|hosting|cloud|cyber|tech\b
industry       промышлен|производств|оборудован|станк|станок|завод|металл|спецтехник|industr|manufactur|machinery|equipment
home           дом(?:а|у|ом|е|ов)?\b|ремонт|мебел|стройматериал|строител|стройк|бытов|сад(?:а|у|ом|ы|ов)?\b|садов|огород|дач|интерьер|декор|сантехник|освещени|garden|furniture|interior|renovation|home\b|diy\b
""")
"""Ниша → тематика. Порядок — приоритет: общие слова (оборудование, ремонт, дом) —
в конце, чтобы «ремонт автомобилей» был «Авто», а «спортивное оборудование» — «Спорт».
«ПО» — только вся ниша целиком (`^по$`): иначе «товары по уходу» стали бы софтом.
Модели в сервисе нет: словарь проверяется тестом и правится строкой; слова ниш прода
13.10.2026 («финтех», «ПО») — оттуда."""

_SITE_WORDS = _words(r"""
marketplace    маркетплейс|marketplace
classifieds    объявлени|classified
aggregator     агрегатор|сравнени\w* (?:цен|тариф)|aggregator|comparison
ecommerce      магазин|ритейл|e-?commerce|e-?shop|webshop|shop|stores?\b|retail
saas           saas|^по$|софт|(?:seo|онлайн|веб)[- ]?инструмент|сервис(?!н)|платформ|приложени|crm\b|облачн|software|platform|apps?\b|cloud
media          медиа|контент|блог|журнал|новост|сми\b|издани|портал|подкаст|media|blog|news|magazine
directory      справочн|энциклопед|баз[аеуы] знаний|каталог|вики|словар|wiki|directory|knowledge base|encyclop
corporate      корпоратив|визитк|сайт компании|corporate|company website
""")
"""Ниша → тип сайта. Совпадения нет — подстановки нет: тип сайта не выводится из
тематики («финансы» бывают и банком, и блогом). Инструмент — сервис, только когда
сказано чей («seo-инструменты»): «музыкальные инструменты» — магазин, а не сервис.
Слова ниш прода 13.10.2026 («ритейл», «софт», «контент», «ПО») — оттуда."""


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


def _prepared_by(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    """Кто вёл проект — пока бриф никто не сохранял: обычно он и рассказывает о кейсе.

    Сохранивший бриф подписывается сам (`api.routers.briefs._sign`), и запись
    вытесняет подстановку — как у любого пункта.
    """
    owner = facts.owner.strip()
    return f"{owner} (вёл проект, из файла)" if owner else ""


def _difficulties(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    """Подсказка по динамике: просадки трафика внутри периода и падение DR от А к Б.

    Настоящие трудности знает специалист — сервис называет только то, что видно в
    купленных цифрах, и просит уточнить причину: копирайтер не должен принять
    подсказку за рассказ о проекте.
    """
    found = [*_traffic_drops(facts), *_rating_drop(facts)]
    if not found:
        return ""
    text = "; ".join(found)
    return f"{text[0].upper()}{text[1:]} (по динамике Ahrefs — уточните причину)"


def _traffic_drops(facts: BriefFacts) -> list[str]:
    """Месяцы периода работ, где трафик упал от `DROP_SHARE` к прошлому месяцу.

    Сравниваются только соседние **измеренные** месяцы: пара через пропуск
    приписала бы одному месяцу падение за два. Месяц до старта в пару не входит —
    просадка до начала работ не трудность работ.
    """
    first, last = _month(facts.period.start), _month(facts.period.end)
    inside = [(at, value) for at, value in facts.traffic if first <= _month(at) <= last]
    drops: list[tuple[float, date, date]] = []
    for (before_at, before), (at, value) in pairwise(inside):
        if before <= 0 or _month(at) - _month(before_at) != 1:
            continue
        share = (value - before) / before
        if share <= -DROP_SHARE:
            drops.append((share, at, before_at))
    deepest = sorted(sorted(drops)[:MAX_DROPS], key=lambda drop: drop[1])
    return [
        f"просадка органического трафика в {at:%m.%Y}: {percent(share * 100)} к {before_at:%m.%Y}"
        for share, at, before_at in deepest
    ]


def _rating_drop(facts: BriefFacts) -> list[str]:
    if facts.rating is None:
        return []
    before, after = facts.rating
    if before - after < RATING_DROP:
        return []
    return [f"Domain Rating снизился: {number(before)} → {number(after)}"]


def _month(at: date) -> int:
    """Номер месяца подряд — соседство и границы периода не зависят от числа в дате."""
    return at.year * 12 + at.month - 1


def _parallel_services(facts: BriefFacts, _brief: Mapping[str, str]) -> str:
    if not facts.parallel:
        return ""
    found = "; ".join(
        f"{service_label(other.service)}, {other.period.start:%m.%Y} — {other.period.end:%m.%Y}"
        for other in facts.parallel
    )
    return f"{found} (тот же домен в базе)"


def _features(facts: BriefFacts, brief: Mapping[str, str]) -> str:
    """YMYL — по тематике, записанной специалистом, а без неё — по словарю ниш."""
    niche = facts.niche.strip()
    topic = brief.get("topic") or (_pick(niche, "topic", _TOPIC_WORDS) if niche else "")
    if topic not in _YMYL:
        return ""
    return (
        "YMYL-тематика: Google строже оценивает экспертность и надёжность сайта "
        f"(по тематике «{_label('topic', topic)}»)"
    )


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
        "prepared_by": _prepared_by,
        "parallel_services": _parallel_services,
        "service_kind": _service_kind,
        "project_kind": _project_kind,
        "site_type": _site_type,
        "topic": _topic,
        "budget": _budget,
        "dynamics_slice": _dynamics_slice,
        "case_period_1": _first_period,
        "features": _features,
        "difficulties": _difficulties,
        "result_weight": _result_weight,
    }
)
"""Пункт брифа → откуда сервис его знает. Пункта нет — его знает только специалист."""
