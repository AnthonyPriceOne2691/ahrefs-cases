"""Подстановка брифа: что сервис знает о пустых пунктах сам — одно правило на лист и карточку.

Примеры приёмки поставки `brief-autofill`: M129 (отдел по услуге), M130 (тип услуги
по периоду), M131 (вид проекта по трафику точки А), M132 (срез и период 1), M133
(весомость по группе), M134 (тематика и тип сайта по нише), M136 (заполненное не
подменяется). Поставки `brief-known-more`: M137 (кто подготовил — кто вёл), M138
(трудности по динамике), M139 (параллельные услуги), M140 (YMYL в особенностях),
M141 (словарь по нишам прода). Правило чистое — база не нужна.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from ahrefs_cases.cases.model import ParallelService, Period
from ahrefs_cases.export.brief_known import (
    DROP_SHARE,
    MAX_DROPS,
    MONTHLY_FROM_MONTHS,
    RATING_DROP,
    BriefFacts,
    known_for,
)
from ahrefs_cases.export.brief_sheet import printed_fields
from ahrefs_cases.storage._enums import Group
from ahrefs_cases.storage.brief import SITE_TYPES, TOPICS

FACTS = BriefFacts(
    niche="финансы",
    work_volume=None,
    service="linkbuilding",
    period=Period(start=date(2026, 5, 1), end=date(2026, 8, 1)),
    group=Group.GOOD,
    traffic_start=2487.0,
    owner="",
    traffic=(),
    rating=None,
    parallel=(),
)


def _known(brief: dict[str, str] | None = None, **facts: Any) -> dict[str, str]:
    return known_for(replace(FACTS, **facts), brief or {})


@pytest.mark.parametrize(
    ("service", "department"),
    [
        ("seo", "SEO (по услуге из файла)"),
        ("linkbuilding", "Линкбилдинг (по услуге из файла)"),
        ("pr", "PR (по услуге из файла)"),
        (" PR ", "PR (по услуге из файла)"),
        ("complex", None),
        ("аудит", None),
    ],
)
def test_department_follows_the_service(service: str, department: str | None) -> None:
    """M129: отдел — по услуге из файла; у «Комплекса» и услуги не из списка подстановки нет."""
    assert _known(service=service).get("department") == department


@pytest.mark.parametrize(
    ("end", "kind"),
    [
        (date(2026, 8, 1), "Ежемесячное продвижение (период 4 мес.)"),
        (date(2026, 7, 1), "Ежемесячное продвижение (период 3 мес.)"),
        (date(2026, 6, 1), "Разовый проект (период 2 мес.)"),
    ],
)
def test_service_kind_follows_the_period(end: date, kind: str) -> None:
    """M130: от трёх месяцев — ежемесячное продвижение, короче — разовый проект."""
    period = Period(start=date(2026, 5, 1), end=end)

    assert MONTHLY_FROM_MONTHS == 3
    assert _known(period=period)["service_kind"] == kind


@pytest.mark.parametrize(
    ("traffic", "kind"),
    [
        (2487.0, "Рост существующего сайта (трафик на старте — 2\u00a0487)"),
        (0.0, "Запуск нового сайта (на старте трафика не было)"),
        (None, None),
    ],
)
def test_project_kind_follows_the_traffic_at_point_a(
    traffic: float | None, kind: str | None
) -> None:
    """M131: трафик в точке А вердикта — рост, ноль — запуск, вердикта нет — подстановки нет."""
    assert _known(traffic_start=traffic).get("project_kind") == kind


def test_whole_period_is_the_default_slice() -> None:
    """M132: срез — весь период работ; период 1 — весь период с услугой, пока срез не «по этапам»."""
    known = _known()
    whole = "05.2026 — 08.2026: Линкбилдинг (период и услуга из файла)"

    assert known["dynamics_slice"] == "Весь период работ (по умолчанию)"
    assert known["case_period_1"] == whole
    assert _known({"dynamics_slice": "whole"})["case_period_1"] == whole
    assert "case_period_1" not in _known({"dynamics_slice": "stages"})
    assert "case_period_2" not in known
    assert _known(service="seo")["case_period_1"].endswith(
        ": SEO-продвижение (период и услуга из файла)"
    )


@pytest.mark.parametrize(
    ("group", "weight"),
    [
        (Group.GOOD, "Высокая (группа «хороший»)"),
        (Group.MEDIUM, "Средняя (группа «средний»)"),
        (Group.POOR, None),
        (Group.INSUFFICIENT_DATA, None),
        (None, None),
    ],
)
def test_result_weight_follows_the_group(group: Group | None, weight: str | None) -> None:
    """M133: «хороший» — высокая, «средний» — средняя; у остальных и без вердикта — нет."""
    assert _known(group=group).get("result_weight") == weight


@pytest.mark.parametrize(
    ("niche", "topic", "site_type"),
    [
        ("финансы", "Финансы (по нише «финансы»)", None),
        (
            "интернет-магазин одежды",
            "Мода и одежда (по нише «интернет-магазин одежды»)",
            "Интернет-магазин (по нише «интернет-магазин одежды»)",
        ),
        (
            "базы знаний",
            "базы знаний (ниша из файла)",
            "Справочник / база знаний (по нише «базы знаний»)",
        ),
        ("зоотовары", "Товары для животных (по нише «зоотовары»)", None),
        ("что-то своё", "что-то своё (ниша из файла)", None),
        ("travel", "Путешествия (по нише «travel»)", None),
        ("", None, None),
    ],
)
def test_topic_and_site_type_follow_the_niche(
    niche: str, topic: str | None, site_type: str | None
) -> None:
    """M134: тематика и тип сайта — по нише; без тематики — сама ниша, без типа — ничего."""
    known = _known(niche=niche)

    assert known.get("topic") == topic
    assert known.get("site_type") == site_type


TOPIC_NICHES = {
    "fashion": "интернет-магазин одежды",
    "travel": "туры в Турцию",
    "health": "медицинская клиника",
    "finance": "ипотека и кредиты",
    "it": "IT-аутсорсинг",
    "auto": "автозапчасти",
    "industry": "промышленное оборудование",
    "home": "товары для дома",
    "pets": "зоотовары",
    "beauty": "косметика",
    "sport": "спортивное питание",
    "food": "доставка еды",
    "entertainment": "онлайн-игры",
    "education": "онлайн-школа английского",
    "hobby": "рукоделие",
}
SITE_NICHES = {
    "ecommerce": "интернет-магазин одежды",
    "marketplace": "маркетплейс электроники",
    "classifieds": "доска объявлений",
    "aggregator": "сравнение цен на авиабилеты",
    "saas": "онлайн-сервис бухгалтерии",
    "media": "новостной портал",
    "directory": "базы знаний",
    "corporate": "корпоративный сайт завода",
}


def test_dictionary_covers_every_topic_and_site_type() -> None:
    """M134: у каждого пункта тематики и типа сайта, кроме «Другое», есть слова в словаре."""
    topics = {choice.key: choice.label for choice in TOPICS if choice.key != "other"}
    sites = {choice.key: choice.label for choice in SITE_TYPES if choice.key != "other"}

    assert set(TOPIC_NICHES) == set(topics)
    assert set(SITE_NICHES) == set(sites)
    for key, niche in TOPIC_NICHES.items():
        assert _known(niche=niche)["topic"] == f"{topics[key]} (по нише «{niche}»)", niche
    for key, niche in SITE_NICHES.items():
        assert _known(niche=niche)["site_type"] == f"{sites[key]} (по нише «{niche}»)", niche


@pytest.mark.parametrize(
    ("niche", "topic"),
    [
        ("доменные имена", "доменные имена (ниша из файла)"),
        # «автоматизация» — не «Авто», а софт: ниша zapier.com на стенде 13.10.
        ("автоматизация бизнеса", "ИТ и софт (по нише «автоматизация бизнеса»)"),  # M134
        ("ремонт автомобилей", "Авто (по нише «ремонт автомобилей»)"),
        ("спортивное оборудование", "Спорт (по нише «спортивное оборудование»)"),
        ("детский сад", "Образование (по нише «детский сад»)"),
        ("Бельё", "Мода и одежда (по нише «Бельё»)"),
        ("Другое", "Другое (ниша из файла)"),
    ],
)
def test_short_and_general_words_do_not_win(niche: str, topic: str) -> None:
    """M134: «дом» не находится в «домене», общие слова уступают точным, «Другое» не выбирается."""
    assert _known(niche=niche)["topic"] == topic


def test_filled_item_is_not_substituted() -> None:
    """M136: заполненный специалистом пункт сервис не подменяет; лист печатает каждый подставленный."""
    full = _known(niche="интернет-магазин одежды", work_volume=120)
    brief = {"department": "pr", "topic": "travel", "budget": "50 000 $", "result_weight": "low"}

    assert set(full) == {
        "department",
        "service_kind",
        "project_kind",
        "site_type",
        "topic",
        "budget",
        "dynamics_slice",
        "case_period_1",
        "result_weight",
    }
    assert set(full) <= printed_fields()
    assert full["budget"] == "120 (объём работ из файла)"
    known = _known(brief, niche="интернет-магазин одежды", work_volume=120)
    assert set(known) == set(full) - set(brief)
    assert known["service_kind"] == full["service_kind"]


@pytest.mark.parametrize(
    ("owner", "brief", "prepared_by"),
    [
        ("Пётр", {}, "Пётр (вёл проект, из файла)"),
        ("  Пётр ", {}, "Пётр (вёл проект, из файла)"),
        ("", {}, None),
        ("Пётр", {"prepared_by": "Анна"}, None),
    ],
)
def test_prepared_by_is_who_led_the_project(
    owner: str, brief: dict[str, str], prepared_by: str | None
) -> None:
    """M137: «Кто подготовил» — «Кто вёл проект» из файла; не сказано — нет; записано — не трогается."""
    assert _known(brief, owner=owner).get("prepared_by") == prepared_by


def _months(*values: float, start: date = date(2026, 5, 1)) -> tuple[tuple[date, float], ...]:
    """Ряд трафика по месяцам подряд от `start`."""
    out = []
    for shift, value in enumerate(values):
        total = start.month - 1 + shift
        out.append((date(start.year + total // 12, total % 12 + 1, 1), value))
    return tuple(out)


TAIL = " (по динамике Ahrefs — уточните причину)"
DROP_07 = "Просадка органического трафика в 07.2026: -18\u00a0% к 06.2026"


@pytest.mark.parametrize(
    ("traffic", "rating", "difficulties"),
    [
        (_months(1000, 1200, 980, 1300), (31.0, 31.0), DROP_07 + TAIL),
        (_months(1000, 1200, 1400, 1600), (32.0, 29.0), "Domain Rating снизился: 32 → 29" + TAIL),
        (
            _months(1000, 1200, 980, 1300),
            (32.0, 29.0),
            DROP_07 + "; Domain Rating снизился: 32 → 29" + TAIL,
        ),
        (_months(1000, 1100, 990, 1300), (32.0, 30.0), None),
        (_months(1300, 1000, 1100, 1200, 1250, start=date(2026, 4, 1)), None, None),
        (((date(2026, 5, 1), 1000.0), (date(2026, 7, 1), 700.0)), None, None),
        ((), None, None),
    ],
    ids=["drop", "rating", "both", "below-threshold", "drop-before-start", "gap", "no-series"],
)
def test_difficulties_hint_from_the_dynamics(
    traffic: tuple[tuple[date, float], ...],
    rating: tuple[float, float] | None,
    difficulties: str | None,
) -> None:
    """M138: просадка трафика от 15 % к прошлому месяцу и падение DR от 3 пунктов — подсказкой.

    Сравниваются соседние измеренные месяцы внутри периода работ 05–08.2026: месяц до
    старта в пару не входит, пара через пропуск не сравнивается.
    """
    assert (DROP_SHARE, RATING_DROP) == (0.15, 3.0)
    assert _known(traffic=traffic, rating=rating).get("difficulties") == difficulties


def test_difficulties_name_the_deepest_drops_in_month_order() -> None:
    """M138: больше трёх просадок — три самые глубокие, по порядку месяцев."""
    period = Period(start=date(2026, 1, 1), end=date(2026, 12, 1))
    # Просадки: 02 −20 %, 04 −50 %, 06 −30 %, 08 −16 %, 10 −40 %.
    traffic = _months(
        1000, 800, 1000, 500, 1000, 700, 1000, 840, 1000, 600, 1000, 1000, start=date(2026, 1, 1)
    )

    found = _known(traffic=traffic, period=period)["difficulties"]

    assert MAX_DROPS == 3
    assert found == (
        "Просадка органического трафика в 04.2026: -50\u00a0% к 03.2026; "
        "просадка органического трафика в 06.2026: -30\u00a0% к 05.2026; "
        "просадка органического трафика в 10.2026: -40\u00a0% к 09.2026" + TAIL
    )


def test_parallel_services_from_the_same_domain() -> None:
    """M139: другие проекты домена — услугой словами и периодом; нет пары — нет подстановки."""
    linkbuilding = ParallelService(
        "linkbuilding", Period(start=date(2025, 6, 1), end=date(2026, 5, 1))
    )
    own_word = ParallelService("аудит", Period(start=date(2025, 9, 1), end=date(2025, 10, 1)))

    assert _known(parallel=(linkbuilding,))["parallel_services"] == (
        "Линкбилдинг, 06.2025 — 05.2026 (тот же домен в базе)"
    )
    assert _known(parallel=(linkbuilding, own_word))["parallel_services"] == (
        "Линкбилдинг, 06.2025 — 05.2026; аудит, 09.2025 — 10.2025 (тот же домен в базе)"
    )
    assert "parallel_services" not in _known()


YMYL = "YMYL-тематика: Google строже оценивает экспертность и надёжность сайта"


@pytest.mark.parametrize(
    ("niche", "brief", "features"),
    [
        ("финансы", {}, YMYL + " (по тематике «Финансы»)"),
        ("авто", {"topic": "health"}, YMYL + " (по тематике «Медицина и здоровье»)"),
        ("медицинская клиника", {}, YMYL + " (по тематике «Медицина и здоровье»)"),
        ("авто", {}, None),
        ("финансы", {"topic": "other"}, None),
        ("финансы", {"features": "сайт на Tilda"}, None),
    ],
)
def test_features_name_ymyl_topics(niche: str, brief: dict[str, str], features: str | None) -> None:
    """M140: финансы и медицина — YMYL; тематика специалиста важнее словаря; записанное не трогается."""
    assert _known(brief, niche=niche).get("features") == features


@pytest.mark.parametrize(
    ("niche", "topic", "site_type"),
    [
        ("seo-инструменты", None, "Сервис / SaaS"),
        ("DIY-ритейл", None, "Интернет-магазин"),
        ("ПО", "ИТ и софт", "Сервис / SaaS"),
        ("софт для разработчиков", "ИТ и софт", "Сервис / SaaS"),
        ("контент", None, "Медиа / блог"),
        ("финтех", "Финансы", None),
    ],
)
def test_dictionary_knows_production_niches(
    niche: str, topic: str | None, site_type: str | None
) -> None:
    """M141: ниши прода 13.10.2026, которых словарь не узнавал, — тематика и тип сайта."""
    known = _known(niche=niche)

    if topic is not None:
        assert known["topic"] == f"{topic} (по нише «{niche}»)"
    if site_type is not None:
        assert known["site_type"] == f"{site_type} (по нише «{niche}»)"


@pytest.mark.parametrize(
    ("niche", "field", "not_this"),
    [
        ("музыкальные инструменты", "site_type", "Сервис / SaaS"),
        ("товары по уходу", "topic", "ИТ и софт"),
        ("ПО-шник на час", "topic", "ИТ и софт"),
    ],
)
def test_dictionary_words_stay_narrow(niche: str, field: str, not_this: str) -> None:
    """M141: «инструменты» без «чьи» — не сервис, «по» внутри ниши — не «ПО»."""
    assert not _known(niche=niche).get(field, "").startswith(not_this)
