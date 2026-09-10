"""Предварительный отбор кандидатов шага 2.

Группу проекта определяет трафик, а дорогие метрики (ключевые слова, ссылки,
срезы) нужны только тем, по кому будет кейс. Отбор здесь **предварительный** и
называется так намеренно: он не пишет `Verdict`, не возвращает группу и не
знает про пороги Приложения А. Настоящую классификацию с объяснением даёт Ф3 и
переопределяет этот отбор — подпись `collect_stage2` при этом не меняется.

Почему вообще нужен: без отбора шаг 2 платится за все сто проектов, включая
те, чей результат заведомо не станет кейсом. В CRM агентства тот же приём
(дешёвый префильтр перед дорогим гейтом) дал экономию 25–40 %.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint

logger = logging.getLogger(__name__)


async def preliminary_candidates(
    session: AsyncSession,
    project_ids: Sequence[int],
    *,
    source: MetricSource,
    min_growth: float | None = None,
) -> list[int]:
    """Проекты, по которым имеет смысл платить за дорогие метрики.

    Правило простое до грубости: органический трафик в конце серии вырос
    относительно начала не меньше чем в `min_growth` раз. Это не оценка
    качества работ — это ответ на вопрос «стоит ли тратить units дальше».
    """
    if not project_ids:
        return []

    threshold = min_growth if min_growth is not None else config.ahrefs.stage2_min_growth
    candidates: list[int] = []
    for project_id in project_ids:
        growth = await _traffic_growth(session, project_id, source)
        if growth is None:
            # Нет данных — не кандидат: платить за дорогие метрики там, где нет
            # даже дешёвых, значит покупать заведомо пустой кейс.
            continue
        if growth >= threshold:
            candidates.append(project_id)

    logger.info(
        "funnel_preliminary_candidates",
        extra={
            "considered": len(project_ids),
            "selected": len(candidates),
            "min_growth": threshold,
        },
    )
    return candidates


async def _traffic_growth(
    session: AsyncSession, project_id: int, source: MetricSource
) -> float | None:
    """Отношение последней точки трафика к первой. `None` — считать не по чему."""
    stmt = select(MetricPoint.point_date, MetricPoint.value).where(
        MetricPoint.project_id == project_id,
        MetricPoint.metric == Metric.ORG_TRAFFIC,
        MetricPoint.source == source,
    )
    rows = sorted((await session.execute(stmt)).all(), key=lambda row: row.point_date)
    if len(rows) < _MIN_POINTS:
        return None

    first = rows[0].value
    last = rows[-1].value
    if first <= 0:
        # Рост с нуля бесконечен по формуле и бессмысленен по сути: такой
        # проект решает Ф3 по абсолютным значениям, а не эта функция.
        return None
    return float(last) / float(first)


_MIN_POINTS = 2
"""Меньше двух точек — сравнивать нечего. Одна точка «выросла» ровно в
столько же раз, во сколько не выросла."""
