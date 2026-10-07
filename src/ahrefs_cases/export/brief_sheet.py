"""Лист брифа: пункты шаблона кейса в его порядке — с тем, что известно.

Пункт шаблона приходит из одного из трёх мест: из входного файла (кто вёл,
услуга, период, гео), из данных Ahrefs (рост показателей) или из брифа, который
заполнил специалист (`storage.brief`). Порядок — шаблона агентства (K117), а не
источников: копирайтер читает лист сверху вниз, как привык читать шаблон.

Пустой пункт печатается словами «заполняет специалист» — пробел виден, а не
пропущен (команда агентства 07.10.2026). Пункт брифа, которого нет на листе,
быть не может: раскладка обязана назвать каждое поле описания, и это
проверяется тестом.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ahrefs_cases.cases.format import number, percent
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.storage.brief import (
    ANALYSIS,
    EMPLOYEE,
    FIELDS_BY_KEY,
    PROJECT,
    RESULTS,
    SERVICES,
    WORKS,
    FieldKind,
    label_of,
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


def _service(case: CaseData) -> str:
    for choice in SERVICES:
        if choice.key == case.service.strip().lower():
            return choice.label
    return case.service


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
        "@service": ("Услуга (по которой пишем кейс)", _service),
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
    return tuple(
        BriefSection(title, tuple(_row(case, key) for key in keys)) for title, keys in LAYOUT
    )


def _row(case: CaseData, key: str) -> BriefRow:
    if key in _AUTO:
        label, compute = _AUTO[key]
        return BriefRow(label, compute(case))
    field = FIELDS_BY_KEY[key]
    value = case.brief.get(key, "")
    if not value:
        value = _fallback(case, key)
    shown = label_of(field, value) if value else ""
    return BriefRow(field.label, shown, link=field.kind is FieldKind.LINK and bool(shown))


def _fallback(case: CaseData, key: str) -> str:
    """То, что файл знает о пункте, пока специалист его не заполнил."""
    if key == "topic":
        return case.niche
    if key == "budget" and case.work_volume is not None:
        return f"{number(float(case.work_volume))} (объём работ из файла)"
    return ""


def printed_fields() -> frozenset[str]:
    """Поля брифа, которые раскладка печатает, — для сверки с описанием брифа."""
    return frozenset(key for _, keys in LAYOUT for key in keys if not key.startswith("@"))
