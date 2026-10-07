"""Ссылки на отчёты Ahrefs для брифа: домен, режим, страна и период уже подставлены.

Скриншоты из Ahrefs — полуавтомат (решение команды агентства 07.10.2026): робот в
интерфейсе Ahrefs — риск блокировки учётки, поэтому сервис кладёт в бриф готовые
ссылки, а специалист открывает их под своей учёткой, снимает экран и загружает.

Отчёты — те, что назвала команда: «Обзор» (органический трафик), «Органические
ключевые слова» (динамика по топам), «Ссылающиеся домены» (ссылочный рост).
Период — от трёх месяцев до старта работ до их конца; страна — гео проекта, у
нескольких стран — по ссылке на каждую, у всего мира — «все страны».

Формат адресов взят из настоящих ссылок интерфейса (с апреля 2026 — без `v2-`),
а не из документации: публичной её у Ahrefs нет. Поэтому ссылка — подсказка, а не
обещание: открывший её человек проверяет период глазами, и лист это говорит.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote, urlencode

from ahrefs_cases.storage.geo import WORLDWIDE, countries, label

APP = "https://app.ahrefs.com/site-explorer"
BEFORE_START_MONTHS = 3
"""Сколько месяцев до старта показывать: «за 3 месяца до старта работ» — команда."""


@dataclass(frozen=True, slots=True)
class ReportLink:
    """Ссылка на отчёт: что за отчёт, по какой стране и куда вести."""

    report: str
    country: str
    url: str


def report_links(
    domain: str, mode: str, geo: str, start: date, end: date
) -> tuple[ReportLink, ...]:
    """Три отчёта команды по каждой стране проекта; у всего мира — один набор."""
    period = f"{_months_before(start, BEFORE_START_MONTHS).isoformat()}|{end.isoformat()}"
    target = {"target": f"{domain}/", "mode": mode}
    codes = countries(geo) or (WORLDWIDE,)
    links: list[ReportLink] = []
    for code in codes:
        shown = label(code)
        overview = code.lower() if code != WORLDWIDE else "all"
        keywords = code.lower() if code != WORLDWIDE else "allByLocation"
        links += [
            ReportLink(
                "Обзор: органический трафик",
                shown,
                _url(
                    "overview",
                    target,
                    country=overview,
                    overview_tab="organic_search",
                    chartInterval=period,
                    chartGranularity="monthly",
                ),
            ),
            ReportLink(
                "Органические ключевые слова: динамика по топам",
                shown,
                _url(
                    "organic-keywords",
                    target,
                    country=keywords,
                    chartInterval=period,
                    chartGranularity="monthly",
                    compareDate="dontCompare",
                ),
            ),
            ReportLink(
                "Ссылающиеся домены: ссылочный рост",
                shown,
                _url("refdomains", target, history="all"),
            ),
        ]
    return tuple(links)


def _url(report: str, target: dict[str, str], **params: str) -> str:
    query = urlencode({**target, **params}, quote_via=quote, safe="")
    return f"{APP}/{report}?{query}"


def _months_before(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 - months
    return date(total // 12, total % 12 + 1, 1)
