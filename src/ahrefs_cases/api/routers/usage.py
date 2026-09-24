"""Расход units: потрачено, зарезервировано, остаток.

Заказчик назвал стоимость запуска на 100 URL метрикой успеха сервиса, а остаток
квоты — поводом для алерта. Оба числа до сих пор существовали только в конце
прогона в консоли; здесь они становятся ответом, который можно показать на
экране.

Остаток берётся у провайдера: в fixture-режиме — без сети и без расхода.

Журнал расхода роутер сам не суммирует: «потрачено» и стоимость на сто доменов
спрашиваются у `budget.spend_summary`, где действует то же правило, что у
вычета из остатка, — условные units фикстур не расход. Своя сумма здесь уже
разошлась с ним однажды (Z38).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import UsageView
from ahrefs_cases.collect.budget import reserved_units, spend_summary, uncounted_spend
from ahrefs_cases.collect.factory import build_quota

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/usage",
    tags=["usage"],
    dependencies=[Depends(require_right("read"))],
)


@router.get("", response_model=UsageView)
async def usage(session: SessionDep) -> UsageView:
    """Сколько units потрачено, сколько удержано резервом и сколько осталось."""
    spend = await spend_summary(session)
    reserved = await reserved_units(session)
    uncounted = await uncounted_spend(session)

    remaining: int | None = None
    try:
        remaining = await build_quota().units_left()
    except Exception as exc:
        # Остаток не узнали — это `null`, а не ноль: ноль означал бы «квота
        # кончилась» и заблокировал бы прогоны (fail-closed живёт в preflight,
        # а не в показометре).
        logger.warning("остаток квоты не получен (%s): %s", type(exc).__name__, exc)

    return UsageView(
        spent=spend.live,
        conditional=spend.conditional,
        reserved=reserved,
        remaining=remaining,
        uncounted=uncounted,
        live_domains=spend.live_domains,
        per_hundred_domains=spend.per_hundred(),
    )
