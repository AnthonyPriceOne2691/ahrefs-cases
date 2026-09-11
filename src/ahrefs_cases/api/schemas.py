"""Схемы ответов API. Ровно то, что нужно экрану, и ничего сверх.

Модели домена наружу не отдаются: у `Project` есть клиент и ответственный, у
`Verdict` — внутренний `ruleset_id`, и решать, что из этого видно снаружи,
должен один явный слой, а не сериализатор по умолчанию.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

MAX_PAGE = 100
"""Потолок выдачи. Не вкус: карточка тянет ряды по месяцам, и «отдать всё»
перестаёт работать незаметно ровно тогда, когда данных станет много."""


class ProjectRow(BaseModel):
    """Строка таблицы проектов: то, по чему сортируют и фильтруют."""

    id: int
    domain: str
    niche: str
    geo: str
    service_type: str
    period_start: date
    period_end: date
    publishable: bool
    status: str
    group: str | None = None
    """`None` — проект не классифицирован действующей версией порогов. Это
    ответ, а не пустота: докупить историю и запустить классификацию."""

    score: float | None = None


class ReasonRow(BaseModel):
    """Одно проверенное условие вердикта — то же, что печатает `explain`."""

    subject: str
    fact: float | None
    threshold: float | None
    passed: bool
    decisive: bool
    note: str = ""


class VerdictView(BaseModel):
    group: str
    score: float
    ruleset_version: str
    decided_at: datetime
    reasons: list[ReasonRow]
    point_a: dict[str, float]
    point_b: dict[str, float]


class SeriesRow(BaseModel):
    """Месячный ряд метрики — под график карточки."""

    metric: str
    points: list[tuple[date, float]]


class ProjectCard(BaseModel):
    project: ProjectRow
    verdict: VerdictView | None
    series: list[SeriesRow]


class CaseRow(BaseModel):
    """Кейс в библиотеке. Имя файла — то самое, что уйдёт клиенту."""

    id: int
    project_id: int
    domain: str
    version: int
    anonymized: bool
    status: str
    created_at: datetime
    filename: str | None = None
    checksum: str | None = None


class UsageView(BaseModel):
    """Расход units: что потрачено, что зарезервировано, что осталось."""

    spent: int
    reserved: int
    remaining: int | None = Field(
        default=None,
        description="Остаток по ответу Ahrefs; `null` — остаток не удалось узнать",
    )
    per_hundred_domains: int | None = None
    """Метрика успеха из ТЗ: стоимость запуска на 100 URL."""


class RunRow(BaseModel):
    """Прогон в журнале: статус, сколько проектов и сколько units."""

    id: int
    status: str
    started_by: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    projects_total: int
    projects_ok: int
    projects_failed: int
    units_estimated: int
    units_actual: int
    error: str = ""


class RunStarted(BaseModel):
    """Ответ на запуск: номер прогона и как он поставлен.

    Номер возвращается сразу, потому что строка прогона создаётся обработчиком,
    а не задачей: иначе на вопрос «что я запустил» ответа бы не было до первого
    обращения к Ahrefs.
    """

    run_id: int
    queued_as: str
