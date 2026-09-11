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


class ComparisonRow(BaseModel):
    """Строка «метрика: было → стало». Та же, что в таблице кейса.

    Подпись и рост считаются **на сервере**: словарь подписей и арифметика
    роста уже существуют для кейса, и вторая копия на фронте разошлась бы с
    первой — экран и PDF начали бы называть метрики по-разному, а рост от
    нулевой базы превратился бы из «не определён» в сто процентов.
    """

    subject: str
    label: str
    before: float
    after: float
    absolute: float
    pct: float | None
    """`None` — рост от нулевой базы: процента у него нет."""


class VerdictView(BaseModel):
    group: str
    score: float
    ruleset_version: str
    decided_at: datetime
    reasons: list[ReasonRow]
    point_a: dict[str, float]
    point_b: dict[str, float]
    comparison: list[ComparisonRow] = []


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


class RulesetRow(BaseModel):
    """Версия порогов в списке. Содержимое отдаётся целиком: его правят."""

    id: int
    version: str
    is_active: bool
    note: str
    created_at: datetime
    payload: dict[str, object]


class RulesetCreate(BaseModel):
    """Новая версия порогов. Имя версии — ключ, и он неизменяем."""

    version: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=500)
    payload: dict[str, object]


class PreviewChange(BaseModel):
    domain: str
    was: str | None
    becomes: str


class PreviewView(BaseModel):
    """Что изменится при этой версии порогов — и чего в этом счёте нет.

    Четыре состояния, а не два: сменит группу, получит вердикт впервые, данных
    этой версии не хватает, не изменится (уроки L31 и L32).
    """

    version: str
    total: int
    changes: list[PreviewChange]
    first_time: list[PreviewChange]
    unchanged: int
    missing_data: list[str]


class AlertView(BaseModel):
    """Повод, о котором оператор должен узнать сам."""

    kind: str
    severity: str
    message: str


class RejectionRow(BaseModel):
    """Отклонённая строка источника: где, что и почему.

    `row_no` — номер строки **в файле**, вместе с заголовком: человек пойдёт
    искать её глазами в Excel, и off-by-one стоит ему минуты на каждой строке.
    """

    row_no: int
    field: str
    reason: str
    detail: str = ""


class IntakeReportView(BaseModel):
    """Итог приёма списка.

    Три числа, а не одно: повторная загрузка того же файла законна и обязана
    выглядеть как «обновлено 93», а не как «принято 93» во второй раз.
    """

    origin: str
    accepted: int
    created: int
    updated: int
    rejected_rows: int
    by_reason: dict[str, int]
    rejections: list[RejectionRow]
    notices: list[RejectionRow] = []
    """Непонятые ячейки **принятых** строк. Отдельным полем, потому что
    последствие другое: проект в сервисе есть, а цифру можно уточнить позже.
    Считать их отказами значило бы показать принятые строки потерянными."""


class IntakeLink(BaseModel):
    """Ссылка на опубликованную Google Sheet — второй способ загрузки по ТЗ."""

    url: str = Field(min_length=1, max_length=2000)


class RunEstimate(BaseModel):
    """Во что обойдётся прогон и можно ли его начинать.

    Вердикт тремя состояниями, а не флагом: «не хватает квоты» лечится
    ожиданием или повышением лимита, «остаток неизвестен» — починкой доступа к
    Ahrefs, и показать человеку не ту причину значит отправить его не туда.
    """

    projects: int
    units_estimated: int
    requests_planned: int
    requests_cached: int
    scheme_lines: list[str]
    quota_left: int | None
    quota_reserved: int
    verdict: str
    may_start: bool
    reason: str = ""


class ChartBlock(BaseModel):
    """Готовый график: заголовок и разметка.

    Отдаётся **рисунком**, а не данными для рисования: решение владельца —
    один SVG идёт и в PDF, и в веб-карточку. Отдай мы точки, у фронта
    появилась бы вторая модель графика, и два рисунка разошлись бы на первой
    же правке — клиент и сотрудник увидели бы разные кривые одного проекта.
    """

    title: str
    svg: str
