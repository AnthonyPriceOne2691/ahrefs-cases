"""Сколько страниц занимает лист «Динамика» в брифе.

С 07.10.2026 PDF — бриф копирайтеру: сначала пункты шаблона (сколько займут),
затем с новой страницы лист «Динамика» — прежний одностраничный кейс, и его
одностраничность — по-прежнему требование макета (урок L45: мерить, а не
надеяться). Лист отмечен в шаблоне комментариями `<!-- sheet -->` … `<!-- /sheet -->`:
страницы листа — это страницы всего документа минус страницы брифа без него.
"""

from __future__ import annotations

from weasyprint import HTML

START, END = "<!-- sheet -->", "<!-- /sheet -->"


def _pages(html: str) -> int:
    return len(HTML(string=html).render().pages)


def sheet_pages(html: str) -> int:
    """Страницы листа «Динамика»; бриф без листа считается отдельно."""
    head, rest = html.split(START, 1)
    _, tail = rest.split(END, 1)
    return _pages(html) - _pages(head + tail)
