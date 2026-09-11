"""Расход units: потрачено, зарезервировано, остаток.

Заказчик назвал стоимость запуска на 100 URL метрикой успеха сервиса, а остаток
квоты — поводом для алерта. Оба числа до сих пор existed только в конце прогона
в консоли; здесь они становятся ответом, который можно показать на экране.

Остаток берётся у провайдера: в fixture-режиме — без сети и без расхода.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import UsageView
from ahrefs_cases.collect.budget import reserved_units
from ahrefs_cases.collect.factory import build_quota
from ahrefs_cases.storage import LedgerKind
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/usage",
    tags=["usage"],
    dependencies=[Depends(require_right("read"))],
)

_HUNDRED = 100


@router.get("", response_model=UsageView)
async def usage(session: SessionDep) -> UsageView:
    """Сколько units потрачено, сколько удержано резервом и сколько осталось."""
    spent = int(
        await session.scalar(
            select(func.coalesce(func.sum(UnitsLedger.units_actual), 0)).where(
                UnitsLedger.kind == LedgerKind.SPENT
            )
        )
        or 0
    )
    reserved = await reserved_units(session)
    projects = int(await session.scalar(select(func.count()).select_from(Project)) or 0)

    remaining: int | None = None
    try:
        remaining = await build_quota().units_left()
    except Exception as exc:
        # Остаток не узнали — это `null`, а не ноль: ноль означал бы «квота
        # кончилась» и заблокировал бы прогоны (fail-closed живёт в preflight,
        # а не в показометре).
        logger.warning("остаток квоты не получен (%s): %s", type(exc).__name__, exc)

    return UsageView(
        spent=spent,
        reserved=reserved,
        remaining=remaining,
        per_hundred_domains=round(spent / projects * _HUNDRED) if projects and spent else None,
    )
