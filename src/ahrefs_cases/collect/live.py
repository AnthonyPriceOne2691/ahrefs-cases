"""Живой провайдер Ahrefs. Пишется сейчас, проверяется в Ф7 — с ключом.

Код здесь не «заглушка на будущее»: если оставить его на потом, к моменту
появления ключа придётся одновременно писать разбор ответа и разбираться с
живым API, и любая ошибка будет выглядеть как проблема Ahrefs. Написанный
заранее, он оставляет к Ф7 ровно один вопрос — совпадает ли форма ответа с
ожидаемой.

Единственное, чего здесь принципиально нет, — проверки на реальных данных.
Поэтому `AHREFS_PROVIDER=live` остаётся решением человека (`delivery/CONSTITUTION.md`).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport
from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.provider import HistoryPoint, HistoryRequest, HistoryResult
from ahrefs_cases.collect.response_guard import (
    ensure_values_parsed,
    require_rows,
    warn_if_not_monthly,
    warn_if_shallower_than_asked,
)
from ahrefs_cases.storage._enums import Metric, MetricSource

logger = logging.getLogger(__name__)


class AhrefsLive:
    """Настоящие запросы к Ahrefs. Реализует `AhrefsProvider`."""

    source = MetricSource.LIVE

    def __init__(self, transport: AhrefsTransport | None = None) -> None:
        self._transport = transport or AhrefsTransport()

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        response = await self._transport.get(spec.path, _params(spec, request))
        rows = require_rows(response.payload, spec.list_key, spec.name)
        points = tuple(_to_point(spec, row) for row in rows if _has_date(row))

        # Строки пришли, а метрик не разобралось — значит имена полей другие.
        # Без этой проверки серия молча состояла бы из пустых точек, и
        # классификация назвала бы живой проект «нет данных».
        parsed = sum(len(point.values) for point in points)
        ensure_values_parsed(rows, parsed, spec.name, tuple(spec.metrics))
        warn_if_not_monthly([point.at for point in points], spec.name, request.target)
        warn_if_shallower_than_asked(
            [point.at for point in points], request.date_from, spec.name, request.target
        )
        return HistoryResult(
            endpoint=spec.name,
            target=request.target,
            points=points,
            units_estimated=response.units_estimated or spec.estimate_units(),
            units_actual=response.units_actual,
            source=self.source,
        )


def _params(spec: EndpointSpec, request: HistoryRequest) -> dict[str, str]:
    """Параметры запроса. `select` — минимальный, и это не стилистика, а деньги.

    `history_grouping` берётся из конфига, а не хардкодится: `daily` на 18
    месяцев это ~550 строк вместо 18, и биллинг считает строки.
    """
    params = {
        "target": request.target,
        "mode": request.mode.value,
        "date_from": request.date_from.isoformat(),
        "history_grouping": config.ahrefs.history_grouping,
        "select": ",".join(spec.select),
        "output": "json",
    }
    if request.date_to is not None:
        params["date_to"] = request.date_to.isoformat()
    if request.country:
        params["country"] = request.country.lower()
    return params


def _has_date(row: dict[str, Any]) -> bool:
    if row.get("date"):
        return True
    logger.warning("ahrefs_row_without_date", extra={"row_keys": sorted(row)})
    return False


def _to_point(spec: EndpointSpec, row: dict[str, Any]) -> HistoryPoint:
    """Строка ответа → точка серии.

    `None` в значении **пропускается**, а не превращается в ноль: «данных за
    месяц нет» и «трафик упал в ноль» — разные вещи, и классификация в Ф3
    обязана их различать (пример B8).
    """
    values: dict[Metric, float] = {}
    for field, metric in spec.metrics.items():
        raw = row.get(field)
        if raw is None:
            continue
        values[metric] = float(raw)
    return HistoryPoint(at=_parse_date(str(row["date"])), values=values)


def _parse_date(raw: str) -> date:
    """`2025-01-01` или `2025-01-01T00:00:00Z` — Ahrefs отдаёт обе формы."""
    text = raw.replace("Z", "+00:00")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return datetime.fromisoformat(text).date()
