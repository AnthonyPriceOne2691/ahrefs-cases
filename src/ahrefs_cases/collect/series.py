"""Ответ history-endpoint'а → строки `MetricPoint`.

Идемпотентность по `(project_id, metric, point_date, source)`: повторный сбор
**обновляет** значение, а не плодит дубли — иначе график показывал бы две линии
за один месяц, а «сколько мы собрали» перестало бы совпадать с «сколько купили».

Запись идёт `ON CONFLICT DO UPDATE` по этому же ключу, а не «прочитать, сравнить,
записать»: два прогона по одному домену (разные отделы, один список) идут
параллельно, и проверка перед записью между ними не удерживается.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.provider import HistoryResult, points_to_rows
from ahrefs_cases.storage.models.metric_point import MetricPoint


async def store_history(session: AsyncSession, project_id: int, result: HistoryResult) -> int:
    """Записать точки ответа. Возвращает число записанных строк метрик."""
    rows = points_to_rows(result)
    if not rows:
        return 0

    now = datetime.now(UTC)
    values = [
        {
            "project_id": project_id,
            "metric": metric,
            "point_date": at,
            "value": value,
            "source": result.source,
            "fetched_at": now,
        }
        for at, metric, value in rows
    ]
    stmt = insert(MetricPoint).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_metric_point_identity",
        set_={"value": stmt.excluded.value, "fetched_at": stmt.excluded.fetched_at},
    )
    await session.execute(stmt)
    return len(values)
