"""Подстановка брифа: что сервис знает о пустых пунктах сам — одно правило на лист и карточку.

Примеры приёмки поставки `brief-autofill`: M129 (отдел по услуге), M130 (тип услуги
по периоду), M131 (вид проекта по трафику точки А), M132 (срез и период 1), M133
(весомость по группе), M134 (тематика и тип сайта по нише), M136 (заполненное не
подменяется). Правило чистое — база не нужна.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from ahrefs_cases.cases.model import Period
from ahrefs_cases.export.brief_known import MONTHLY_FROM_MONTHS, BriefFacts, known_for
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
        ("автоматизация бизнеса", "автоматизация бизнеса (ниша из файла)"),
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
