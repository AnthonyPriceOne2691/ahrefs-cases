"""Лист брифа: пункты шаблона кейса в его порядке — с тем, что известно.

Пункт шаблона приходит из одного из трёх мест: из входного файла (кто вёл,
услуга, период, гео), из данных Ahrefs (рост показателей) или из брифа, который
заполнил специалист (`storage.brief`). Порядок — шаблона агентства (K117), а не
источников: копирайтер читает лист сверху вниз, как привык читать шаблон.

Пустой пункт брифа печатает то, что сервис знает о нём сам, с источником в
скобках (`brief_known`, то же правило у карточки), а без этого — «заполняет
специалист»: пробел виден, а не пропущен (команда агентства 07.10.2026). Пункт
брифа, которого нет на листе, быть не может: раскладка обязана назвать каждое
поле описания, и это проверяется тестом.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ahrefs_cases.cases.format import percent
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.export.brief_known import BriefFacts, known_for
from ahrefs_cases.storage._enums import Metric
from ahrefs_cases.storage.brief import (
    ANALYSIS,
    EMPLOYEE,
    FIELDS_BY_KEY,
    PROJECT,
    RESULTS,
    WORKS,
    FieldKind,
    label_of,
    service_label,
)

EMPTY = "заполняет специалист"


@dataclass(frozen=True, slots=True)
class BriefRow:
    label: str
    value: str
    """Пусто — пункт не заполнен; шаблон печатает «заполняет специалист»."""

    link: bool = False


@dataclass(frozen=True, slots=True)
class BriefSection:
    title: str
    rows: tuple[BriefRow, ...]


def _geo(case: CaseData) -> str:
    """Страны словами и, если ряды куплены не по первой из них, оговорка (Z53)."""
    return case.geo_label if case.geo_note is None else f"{case.geo_label}; {case.geo_note}"


def _period(case: CaseData) -> str:
    start, end = case.period.start, case.period.end
    return f"{start:%m.%Y} — {end:%m.%Y} ({case.period.months} мес.)"


def _growth(case: CaseData) -> str:
    shown = [f"{change.label} {percent(change.pct)}" for change in case.changes if change.grew]
    return "; ".join(shown)


def _screens(case: CaseData) -> str:
    """Пункт шаблона — про Ahrefs; скрины видимости в ИИ названы отдельно, чтобы счёт сходился."""
    ahrefs = sum(1 for image in case.screenshots if image.kind == "ahrefs")
    ai = len(case.screenshots) - ahrefs
    told = (
        f"{ahrefs} шт. — в разделе «Скрины» ниже"
        if ahrefs
        else "ещё не загружены: снимите по ссылкам ниже и загрузите в карточку проекта"
    )
    if not ai:
        return told
    if ahrefs:
        return f"{told}; там же видимость в ИИ — {ai} шт."
    return f"{told}; видимость в ИИ — {ai} шт. в разделе «Скрины» ниже"


_AUTO: Mapping[str, tuple[str, Callable[[CaseData], str]]] = MappingProxyType(
    {
        "@owner": ("Кто из сотрудников вёл проект", lambda case: case.owner),
        "@service": ("Услуга (по которой пишем кейс)", lambda case: service_label(case.service)),
        "@period": ("Период сотрудничества", _period),
        "@geo": ("ГЕО", _geo),
        "@growth": ("Процент роста показателей", _growth),
        "@dynamics": (
            "Динамика показателей (подробно)",
            lambda _: "лист «Динамика» в конце брифа: точки А и Б, графики, текст",
        ),
        "@screens": ("Скрины результатов работ из Ahrefs", _screens),
    }
)
"""Пункты, которые сервис заполняет сам. Ключ с `@` — чтобы не спутать с полем брифа."""

LAYOUT: tuple[tuple[str, tuple[str, ...]], ...] = (
    (EMPLOYEE, ("@owner", "department", "prepared_by")),
    (
        PROJECT,
        (
            "@service",
            "parallel_services",
            "service_kind",
            "@period",
            "project_kind",
            "site_type",
            "@geo",
            "topic",
            "language_versions",
            "budget",
        ),
    ),
    (ANALYSIS, ("dynamics_slice", "case_period_1", "case_period_2", "case_period_3")),
    (WORKS, ("client_request", "goals", "works_done", "features", "difficulties")),
    (
        RESULTS,
        (
            "result_weight",
            "complexity",
            "complexity_note",
            "@growth",
            "@dynamics",
            "@screens",
            "folder_url",
        ),
    ),
)
"""Раскладка листа по разделам шаблона: что за чем стоит."""


def brief_sections(case: CaseData) -> tuple[BriefSection, ...]:
    """Разделы листа брифа с тем, что известно о проекте."""
    known = known_for(_facts(case), case.brief)
    return tuple(
        BriefSection(title, tuple(_row(case, key, known) for key in keys)) for title, keys in LAYOUT
    )


def _facts(case: CaseData) -> BriefFacts:
    """Факты кейса для подстановки — те же, что карточка берёт из проекта и вердикта.

    Трафик на старте — «было» строки трафика в таблице А → Б листа: вид проекта
    судится по точке А вердикта, тем числом, что копирайтер видит рядом (L41).
    """
    traffic = case.change(Metric.ORG_TRAFFIC.value)
    return BriefFacts(
        niche=case.niche,
        work_volume=case.work_volume,
        service=case.service,
        period=case.period,
        group=case.group,
        traffic_start=traffic.before if traffic is not None else None,
    )


def _row(case: CaseData, key: str, known: Mapping[str, str]) -> BriefRow:
    if key in _AUTO:
        label, compute = _AUTO[key]
        return BriefRow(label, compute(case))
    field = FIELDS_BY_KEY[key]
    value = case.brief.get(key, "")
    if not value:
        return BriefRow(field.label, known.get(key, ""))
    return BriefRow(field.label, label_of(field, value), link=field.kind is FieldKind.LINK)


def printed_fields() -> frozenset[str]:
    """Поля брифа, которые раскладка печатает, — для сверки с описанием брифа."""
    return frozenset(key for _, keys in LAYOUT for key in keys if not key.startswith("@"))
