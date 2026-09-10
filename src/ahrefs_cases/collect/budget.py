"""Расход units: строка журнала на каждый запрос к провайдеру.

Ф2а ведёт **факт**: сколько запросов сделано и во что они обошлись. Смета,
резервы и мягкий стоп — Ф2б; они опираются на этот же журнал, поэтому он должен
существовать раньше и заполняться одинаково в обоих режимах.

В fixture-режиме units условные, но считаются моделью стоимости живого API
(`EndpointSpec.estimate_units`). Ноль здесь означал бы, что экран расхода и
смета разрабатываются на нулях и проверяются впервые в Ф7 — на деньгах заказчика.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.provider import HistoryResult
from ahrefs_cases.storage._enums import LedgerKind
from ahrefs_cases.storage.models.units_ledger import UnitsLedger


async def record_spend(session: AsyncSession, run_id: int, result: HistoryResult) -> None:
    """Записать стоимость одного ответа провайдера."""
    session.add(
        UnitsLedger(
            run_id=run_id,
            kind=LedgerKind.SPENT,
            endpoint=result.endpoint,
            target=result.target,
            units_estimated=result.units_estimated,
            units_actual=result.units_actual,
            rows=len(result.points),
        )
    )


async def record_cached(session: AsyncSession, run_id: int, endpoint: str, target: str) -> None:
    """Записать запрос, которого не было: цена 0, вид `cached`.

    Строка нужна не для бухгалтерии — экономия обязана быть **предъявляемой**.
    Заказчик меряет сервис «стоимостью запуска на 100 URL»: без этих строк
    второй прогон выглядел бы как прогон, который ничего не делал, и объяснить
    разницу в счёте было бы нечем.
    """
    session.add(
        UnitsLedger(
            run_id=run_id,
            kind=LedgerKind.CACHED,
            endpoint=endpoint,
            target=target,
            units_estimated=0,
            units_actual=0,
            rows=0,
        )
    )


async def run_saved(session: AsyncSession, run_id: int) -> int:
    """Сколько запросов прогон **не** сделал благодаря кэшу."""
    stmt = select(func.count()).where(
        UnitsLedger.run_id == run_id, UnitsLedger.kind == LedgerKind.CACHED
    )
    return int((await session.execute(stmt)).scalar_one())


async def run_spend(session: AsyncSession, run_id: int) -> int:
    """Сколько units стоил прогон по журналу.

    Считается запросом, а не суммированием по дороге: журнал — источник правды о
    расходе, и второй счётчик рано или поздно разойдётся с ним именно в тот
    прогон, который придётся объяснять.
    """
    stmt = select(func.coalesce(func.sum(UnitsLedger.units_actual), 0)).where(
        UnitsLedger.run_id == run_id, UnitsLedger.kind == LedgerKind.SPENT
    )
    total: int | None = (await session.execute(stmt)).scalar_one()
    return total or 0
