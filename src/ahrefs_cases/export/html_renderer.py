"""HTML кейса — источник истины для PDF и будущей веб-карточки.

Один шаблон на оба формата: печатный лист и карточка в интерфейсе обязаны
показывать одно и то же, иначе «по PDF у нас +139 %, а на экране +142 %» станет
вопросом к данным, а не к вёрстке.

**Форматирование меняет вид, а не значение** (урок L41). Число в HTML — то же
число, что в структуре кейса: разделитель тысяч, знак процента и округление
живут здесь, а сами величины приходят из вердикта.

Автоэкранирование включено: ниша, тип услуг и заголовок приходят из файла
заказчика, а не из нашего кода.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ahrefs_cases import config
from ahrefs_cases.cases.format import number, percent
from ahrefs_cases.cases.model import CaseData, CaseSeries, Change
from ahrefs_cases.classify.points import KW_TOP10
from ahrefs_cases.export.charts import SUBJECT_COLORS, curves_svg
from ahrefs_cases.storage._enums import Metric

TEMPLATE_NAME = "case.html.j2"

DATA_FOOTNOTE = (
    "Данные: Ahrefs. Органический трафик — оценка Ahrefs по видимости сайта, "
    "а не фактические визиты из систем аналитики."
)
"""Обязательная сноска (ответ Q4 ТЗ). Живёт в коде, а не только в шаблоне:
её наличие проверяется тестом, а шаблон может быть переверстан кем угодно."""

ATTRIBUTION = "Динамика показана за период работ: рост после старта работ."
"""Атрибуция результата. Формулировка юридическая, а не стилистическая:
«благодаря работам» утверждает причинно-следственную связь, которой у нас нет."""

MAIN_SUBJECT = "org_traffic"
"""Главная метрика ТЗ. Она же определяет группу проекта, поэтому она же стоит
крупно наверху: кейс, который ведёт с Domain Rating, обсуждают не о результате."""

TILE_COUNT = 3


def render_html(case: CaseData, *, templates_dir: Path | None = None) -> str:
    """Кейс → HTML одной страницей."""
    template = _environment(templates_dir).get_template(TEMPLATE_NAME)
    hero = case.change(MAIN_SUBJECT)
    rest = [change for change in case.changes if change is not hero]
    return template.render(
        case=case,
        hero=hero,
        tiles=rest[:TILE_COUNT],
        rows=case.changes,
        charts=charts(case),
        colors=SUBJECT_COLORS,
        footnote=DATA_FOOTNOTE,
        attribution=ATTRIBUTION,
    )


def charts(case: CaseData) -> list[dict[str, str]]:
    """Два графика ТЗ: динамика трафика и динамика позиций.

    Позиции — одна картинка на два ряда: топ-10 и вложенный в него топ-3.
    Порознь они читались бы как независимые метрики, хотя второй входит в
    первый. Ряда нет — графика нет: пустые оси сказали бы «роста не было».
    """
    by_subject = {item.subject: item for item in case.series}
    blocks: list[dict[str, str]] = []
    for title, subjects in (
        ("Динамика органического трафика", (Metric.ORG_TRAFFIC.value,)),
        ("Динамика позиций", (KW_TOP10, Metric.KW_TOP3.value)),
    ):
        rows: list[CaseSeries] = [by_subject[name] for name in subjects if name in by_subject]
        svg = curves_svg(
            rows,
            period_start=case.period.start,
            window_a=case.window_a,
            window_b=case.window_b,
        )
        if svg:
            blocks.append({"title": title, "svg": svg})
    return blocks


def _environment(templates_dir: Path | None) -> Environment:
    """Jinja2 с автоэкранированием и строгими переменными.

    `StrictUndefined` намеренно: опечатка в имени переменной обязана падать, а
    не печатать пустое место в кейсе, который уйдёт клиенту.
    """
    root = templates_dir or config.export.templates_dir
    environment = Environment(
        loader=FileSystemLoader(root),
        autoescape=select_autoescape(default_for_string=True, default=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["num"] = number
    environment.filters["growth"] = growth
    return environment


def growth(change: Change) -> str:
    """Рост метрики для шаблона. Форматирование — `cases.format`, один на всех."""
    return percent(change.pct)
