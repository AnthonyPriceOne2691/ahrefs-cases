"""Чтение списка проектов из опубликованной Google Sheet.

ТЗ разрешает подавать список ссылкой на таблицу, и это единственный сетевой путь
всего сбора на фикстурах. Читаем CSV-экспорт: он не требует ни ключа, ни
сервисного аккаунта — только доступ «по ссылке», который отдел и так выдаёт,
пересылая таблицу.

Приватная таблица сюда не годится и не должна выглядеть так, будто годится:
Google отвечает на неё страницей входа со статусом 200, поэтому HTML в ответе
трактуется как отказ в доступе, а не как пустой список (см. `_ensure_csv`).
Настоящий приватный доступ появится в Ф5, где будет где хранить креды.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx

from ahrefs_cases.intake.csv_source import decode, parse_csv_text
from ahrefs_cases.intake.rows import RawTable

Fetcher = Callable[[str], bytes]
"""Загрузка байтов по ссылке. Параметром, а не импортом: тест подставляет свою и
проверяет разбор без сети — сеть проверяется отдельно и в одном месте."""

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/(?P<id>[a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#&?]gid=(?P<gid>\d+)")
_EXPORT_TEMPLATE = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
_TIMEOUT_SEC = 30.0
_HTML_MARKERS = (b"<!doctype html", b"<html")


class SheetLinkError(ValueError):
    """Ссылка не опознана как Google Sheet. Отдельный тип — чтобы приём отличал
    «список не прочитан» от «список прочитан и пуст»."""


class SheetAccessError(RuntimeError):
    """Таблица недоступна по ссылке: Google вернул страницу, а не CSV."""


def sheet_export_url(link: str) -> str:
    """Ссылка на таблицу → ссылка на CSV-экспорт нужного листа.

    Отдельная чистая функция: форм ссылки много (`/edit#gid=`, `/edit?gid=`,
    `?usp=sharing`, уже готовый `/export`), и разбирать их внутри загрузки
    значило бы проверять их только с сетью.
    """
    match = _SHEET_ID_RE.search(link)
    if not match:
        raise SheetLinkError(f"не похоже на ссылку Google Sheet: {link}")

    gid_match = _GID_RE.search(link)
    gid = gid_match.group("gid") if gid_match else "0"
    return _EXPORT_TEMPLATE.format(sheet_id=match.group("id"), gid=gid)


def read_gsheet(link: str, fetch: Fetcher | None = None) -> RawTable:
    """Опубликованная таблица → сырая таблица, тем же путём, что CSV из файла."""
    url = sheet_export_url(link)
    data = (fetch or _http_fetch)(url)
    _ensure_csv(data, link)

    return parse_csv_text(decode(data), origin=link)


def _http_fetch(url: str) -> bytes:
    response = httpx.get(url, timeout=_TIMEOUT_SEC, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _ensure_csv(data: bytes, link: str) -> None:
    """HTML вместо CSV означает «нет доступа», а не «нет строк».

    Google отвечает на закрытую таблицу страницей входа со статусом 200. Без этой
    проверки приём отчитался бы «принято 0, отклонено 0» — то есть соврал бы
    успехом.
    """
    head = data[:200].lstrip().lower()
    if any(head.startswith(marker) for marker in _HTML_MARKERS):
        raise SheetAccessError(
            f"таблица недоступна по ссылке (Google вернул HTML, а не CSV): {link}. "
            "Откройте доступ «по ссылке» или выгрузите список файлом."
        )
