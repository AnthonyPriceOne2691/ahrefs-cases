"""Бриф копирайтеру: пункты шаблона кейса, которые знает только специалист.

Шаблон агентства (K117 «Кейсохранилища») — пять разделов. Часть пунктов сервис
заполняет сам: URL, кто вёл, услуга, период, гео, динамика и рост — из файла и
Ahrefs. Остальное — здесь: поля, которые человек заполняет в карточке проекта
(у части — колонкой входного файла, чтобы пачкой), и списки значений для
выпадающих. Описание одно на хранение, правку, приём файла и лист PDF: поля,
которого здесь нет, не примут ни API, ни файл.

Значения хранятся ключами (`seo`, `marketplace`), а показываются подписями:
подпись можно переписать, не трогая записанное. Списки собраны 07.10.2026 из
ТЗ (отделы), данных прода (услуги; тематики и типы сайтов, перемешанные в
нишах загруженных файлов) и ответов команды (шкала сложности — подтвердил
владелец); тип услуги, вид проекта и срез динамики — предложение до сверки с
листом шаблона. Правятся здесь, строкой.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from urllib.parse import urlsplit


class FieldKind(StrEnum):
    TEXT = "text"
    LONG_TEXT = "long_text"
    CHOICE = "choice"
    LINK = "link"


@dataclass(frozen=True, slots=True)
class Choice:
    key: str
    label: str


@dataclass(frozen=True, slots=True)
class BriefField:
    """Пункт шаблона. `column` — колонка входного файла; пусто — только карточка."""

    key: str
    label: str
    section: str
    kind: FieldKind
    choices: tuple[Choice, ...] = ()
    column: str = ""

    @property
    def max_len(self) -> int:
        return _MAX_LEN[self.kind]


@dataclass(frozen=True, slots=True)
class BriefRejected:
    """Значение не годится. `detail` — что именно, словами для человека."""

    detail: str


_MAX_LEN = MappingProxyType(
    {FieldKind.TEXT: 300, FieldKind.LONG_TEXT: 3000, FieldKind.CHOICE: 60, FieldKind.LINK: 500}
)
_DRIVE_HOSTS = frozenset({"drive.google.com", "docs.google.com"})

EMPLOYEE, PROJECT, ANALYSIS = "Инфо о сотруднике", "Проект", "Анализ данных"
WORKS, RESULTS = "Выполненные работы", "Результаты работы"
SECTIONS = (EMPLOYEE, PROJECT, ANALYSIS, WORKS, RESULTS)
"""Разделы в порядке шаблона — в нём их показывают карточка и лист."""


def _choices(*pairs: tuple[str, str]) -> tuple[Choice, ...]:
    return tuple(Choice(key, label) for key, label in pairs)


DEPARTMENTS = _choices(
    ("seo", "SEO"), ("linkbuilding", "Линкбилдинг"), ("pr", "PR"), ("other", "Другое")
)
SERVICES = _choices(
    ("seo", "SEO-продвижение"),
    ("linkbuilding", "Линкбилдинг"),
    ("pr", "PR"),
    ("complex", "Комплекс"),
)
"""Услуга кейса — та же колонка `service_type` файла; подписи — для листа."""

SERVICE_KINDS = _choices(
    ("monthly", "Ежемесячное продвижение"),
    ("one_off", "Разовый проект"),
    ("audit", "Аудит / консультация"),
)
PROJECT_KINDS = _choices(
    ("growth", "Рост существующего сайта"),
    ("launch", "Запуск нового сайта"),
    ("recovery", "Восстановление после падения"),
    ("migration", "Переезд / редизайн"),
    ("new_country", "Выход в новую страну"),
)
SITE_TYPES = _choices(
    ("ecommerce", "Интернет-магазин"),
    ("marketplace", "Маркетплейс"),
    ("classifieds", "Доска объявлений"),
    ("aggregator", "Агрегатор / сравнение цен"),
    ("saas", "Сервис / SaaS"),
    ("media", "Медиа / блог"),
    ("directory", "Справочник / база знаний"),
    ("corporate", "Корпоративный сайт"),
    ("other", "Другое"),
)
TOPICS = _choices(
    ("fashion", "Мода и одежда"),
    ("travel", "Путешествия"),
    ("health", "Медицина и здоровье"),
    ("finance", "Финансы"),
    ("it", "ИТ и софт"),
    ("auto", "Авто"),
    ("industry", "Промышленность"),
    ("home", "Дом, сад и ремонт"),
    ("pets", "Товары для животных"),
    ("beauty", "Красота"),
    ("sport", "Спорт"),
    ("food", "Еда"),
    ("entertainment", "Игры и развлечения"),
    ("education", "Образование"),
    ("hobby", "Хобби"),
    ("other", "Другое"),
)
DYNAMICS_SLICES = _choices(
    ("whole", "Весь период работ"), ("stages", "По этапам (до трёх периодов)")
)
RESULT_WEIGHTS = _choices(("high", "Высокая"), ("medium", "Средняя"), ("low", "Низкая"))
COMPLEXITY = _choices(
    ("low", "Низкая"), ("medium", "Средняя"), ("high", "Высокая"), ("very_high", "Очень высокая")
)
"""Шкала сложности — решение владельца 07.10.2026. Поле необязательное: пустое на
листе — «не заполнено», сборку не держит; клиент сложность не видит."""


def _period(number: int) -> BriefField:
    label = f"Период для кейса {number} — какие услуги делали в этот момент"
    return BriefField(f"case_period_{number}", label, ANALYSIS, FieldKind.TEXT)


FIELDS: tuple[BriefField, ...] = (
    BriefField("department", "Чей отдел вёл проект", EMPLOYEE, FieldKind.CHOICE, DEPARTMENTS),
    BriefField("prepared_by", "Кто подготовил информацию по кейсу", EMPLOYEE, FieldKind.TEXT),
    BriefField(
        "parallel_services", "Какие услуги проводились параллельно", PROJECT, FieldKind.TEXT
    ),
    BriefField("service_kind", "Тип услуги", PROJECT, FieldKind.CHOICE, SERVICE_KINDS),
    BriefField("project_kind", "Вид проекта", PROJECT, FieldKind.CHOICE, PROJECT_KINDS),
    BriefField("topic", "Тематика", PROJECT, FieldKind.CHOICE, TOPICS, column="topic"),
    BriefField("site_type", "Тип сайта", PROJECT, FieldKind.CHOICE, SITE_TYPES, column="site_type"),
    BriefField("language_versions", "Языковые версии", PROJECT, FieldKind.TEXT),
    BriefField("budget", "Бюджет проекта / объём работ", PROJECT, FieldKind.TEXT),
    BriefField("dynamics_slice", "Срез динамики", ANALYSIS, FieldKind.CHOICE, DYNAMICS_SLICES),
    _period(1),
    _period(2),
    _period(3),
    BriefField(
        "client_request",
        "Запрос клиента на входе",
        WORKS,
        FieldKind.LONG_TEXT,
        column="client_request",
    ),
    BriefField("goals", "Поставленные цели", WORKS, FieldKind.LONG_TEXT),
    BriefField("works_done", "Выполненные работы", WORKS, FieldKind.LONG_TEXT),
    BriefField("features", "Особенности проекта", WORKS, FieldKind.LONG_TEXT),
    BriefField("difficulties", "Трудности, которые возникли", WORKS, FieldKind.LONG_TEXT),
    BriefField(
        "complexity",
        "Сложность проекта",
        RESULTS,
        FieldKind.CHOICE,
        COMPLEXITY,
        column="complexity",
    ),
    BriefField(
        "complexity_note",
        "Комментарий к сложности",
        RESULTS,
        FieldKind.TEXT,
        column="complexity_note",
    ),
    BriefField("result_weight", "Весомость результата", RESULTS, FieldKind.CHOICE, RESULT_WEIGHTS),
    BriefField(
        "folder_url", "Папка проекта на Google Drive", RESULTS, FieldKind.LINK, column="folder_url"
    ),
)

FIELDS_BY_KEY: Mapping[str, BriefField] = MappingProxyType({field.key: field for field in FIELDS})


def normalize(field: BriefField, raw: str) -> str | BriefRejected:
    """Значение поля → то, что хранится, или причина отказа. Пусто — «очистить».

    Пункт списка узнаётся и ключом, и подписью без учёта регистра: в файле его
    пишут словами, а API присылает ключ. Ссылка — только https на Google Drive:
    другой адрес на листе копирайтера был бы ссылкой неизвестно куда.
    """
    value = raw.strip()
    if not value:
        return ""
    if len(value) > field.max_len:
        return BriefRejected(f"длиннее {field.max_len} символов")
    if field.kind is FieldKind.CHOICE:
        return _choice(field, value)
    if field.kind is FieldKind.LINK:
        return _drive_link(value)
    return value


def label_of(field: BriefField, value: str) -> str:
    """Подпись записанного значения; ключ, которого в списке больше нет, — как есть."""
    for choice in field.choices:
        if choice.key == value:
            return choice.label
    return value


def _choice(field: BriefField, value: str) -> str | BriefRejected:
    wanted = value.casefold()
    for choice in field.choices:
        if wanted in (choice.key.casefold(), choice.label.casefold()):
            return choice.key
    allowed = ", ".join(choice.label for choice in field.choices)
    return BriefRejected(f"«{value}» не из списка: {allowed}")


def _drive_link(value: str) -> str | BriefRejected:
    parts = urlsplit(value)
    if parts.scheme != "https" or (parts.hostname or "") not in _DRIVE_HOSTS:
        return BriefRejected("нужна ссылка https://drive.google.com/… на папку проекта")
    return value
