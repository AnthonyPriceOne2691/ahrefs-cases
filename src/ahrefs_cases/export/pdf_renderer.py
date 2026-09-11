"""HTML кейса → PDF на диске.

Печать — последний шаг, и единственный, после которого ошибка становится
видимой клиенту. Поэтому порядок здесь важнее кода: **сначала стоп-лист, потом
файл**. Проверка, стоящая после записи, защищает уже выданный артефакт.

Сеть при рендере запрещена не обещанием, а загрузчиком ресурсов: любой внешний
адрес в шаблоне обрывает сборку. Сервер агентства может стоять без выхода
наружу, и «кейс собрался, только без картинок» — худший из исходов.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError

from ahrefs_cases import config
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.cases.stoplist import ensure_publishable
from ahrefs_cases.export.html_renderer import render_html

_UNSAFE_IN_NAME = re.compile(r"[^\w.\- ]+", re.UNICODE)
"""Пробел разрешён: «сайт в нише travel — Кейс.pdf» — имя из ТЗ, а не slug."""


@dataclass(frozen=True, slots=True)
class RenderedCase:
    """Готовый артефакт: где лежит и на скольких страницах поместился.

    Число страниц — не справка: одностраничность кейса это требование макета,
    и проверяется оно здесь, а не глазами на каждом прогоне.
    """

    path: Path
    pages: int


class NetworkAccessDeniedError(RuntimeError):
    """Шаблон попросил внешний ресурс. Рендер кейса в сеть не ходит."""


class _DenyNetwork:
    """Загрузчик ресурсов WeasyPrint, который ничего не загружает.

    Класс, а не функция, из-за протокола WeasyPrint: без атрибута
    `_fail_on_errors` исключение загрузчика превращается в **предупреждение**, и
    рендер продолжается без ресурса. То есть запрет, написанный самым очевидным
    способом, дал бы «кейс собрался, только без картинки» — ровно тот исход,
    ради запрета которого он писался.
    """

    _fail_on_errors = True

    def __call__(self, url: str) -> dict[str, Any]:
        message = f"рендер кейса не ходит в сеть, а шаблон запросил {url!r}"
        raise NetworkAccessDeniedError(message)


def render_pdf(
    case: CaseData,
    *,
    output_dir: Path | None = None,
    templates_dir: Path | None = None,
) -> RenderedCase:
    """Собрать PDF кейса. Стоп-лист — до записи файла, а не после."""
    ensure_publishable(case)
    html = render_html(case, templates_dir=templates_dir)
    try:
        document = HTML(string=html, url_fetcher=_DenyNetwork()).render()
    except FatalURLFetchingError as exc:
        # Наружу уходит наша ошибка, а не библиотечная: запрет сети — условие
        # этого модуля, и вызывающий ловит его по нашему имени.
        message = f"рендер кейса не ходит в сеть: {exc}"
        raise NetworkAccessDeniedError(message) from exc

    target = (output_dir or config.export.output_dir) / filename(case)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.write_pdf(target)
    return RenderedCase(path=target, pages=len(document.pages))


def filename(case: CaseData) -> str:
    """Имя файла по ТЗ: «название сайта + Кейс», у непубличных — «сайт в нише X».

    Название берётся из заголовка кейса, а он анонимность уже решил (Q12):
    второе решение о публикуемости здесь завело бы третье место, где она может
    разойтись. Кириллица не транслитерируется — `zipfile` пишет имена в UTF-8.
    """
    stem = _UNSAFE_IN_NAME.sub(" ", case.title.strip()).strip()
    return f"{stem or 'Сайт'} — Кейс.pdf"
