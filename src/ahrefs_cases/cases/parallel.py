"""Параллельные услуги: другие проекты того же домена в базе.

Пункт брифа «Какие услуги проводились параллельно» сервис знает, когда сайт
загружен дважды — разными отделами (zooplus.de на проде: SEO 09.2024–08.2025 и
линкбилдинг 06.2025–05.2026). Пара ищется по домену, а не по клиенту: клиента в
файле пишут свободно, домен — канон. Читают двое — сборка кейса
(`builder._attempt`) и карточка проекта, — поэтому запрос один здесь, а не
копия в каждом (L258).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases.model import ParallelService, Period
from ahrefs_cases.storage.models.project import Project


async def parallel_services(session: AsyncSession, project: Project) -> tuple[ParallelService, ...]:
    """Проекты того же домена с другой услугой, чей период пересекает период проекта.

    Та же услуга — не «параллельная», а другая кампания (или повтор строки), её
    пункт не называет. Порядок — по началу периода и id: порядок кучи Postgres
    меняется от каждого `UPDATE` (L218), а бриф обязан печататься одинаково.
    """
    service = func.lower(func.trim(Project.service_type))
    stmt = (
        select(Project.service_type, Project.period_start, Project.period_end)
        .where(
            Project.domain == project.domain,
            Project.id != project.id,
            service != project.service_type.strip().lower(),
            Project.period_start <= project.period_end,
            Project.period_end >= project.period_start,
        )
        .order_by(Project.period_start, Project.id)
    )
    rows = (await session.execute(stmt)).all()
    return tuple(
        ParallelService(
            service=row.service_type, period=Period(start=row.period_start, end=row.period_end)
        )
        for row in rows
    )
