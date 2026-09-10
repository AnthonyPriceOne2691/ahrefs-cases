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
from ahrefs_cases.storage._enums import LedgerKind, RunStatus
from ahrefs_cases.storage.models.run import Run
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


async def reserve(session: AsyncSession, run_id: int, units: int) -> None:
    """Списать смету прогона резервом.

    Без резерва «кнопка неактивна при нехватке квоты» защищает только первого
    нажавшего: шесть человек, готовящих прогоны одновременно, увидят один и тот
    же остаток и запустятся все. Резерв делает чужие намерения видимыми.
    """
    session.add(
        UnitsLedger(
            run_id=run_id,
            kind=LedgerKind.RESERVE,
            endpoint="",
            target="",
            units_estimated=units,
            units_actual=None,
        )
    )


async def reserved_units(session: AsyncSession) -> int:
    """Сколько units зарезервировано прогонами, которые ещё идут.

    Считается по **активным** прогонам, а не по всем строкам резерва: снимать
    резерв компенсирующей записью значило бы иметь два способа сказать одно и
    то же, и они разошлись бы на первом же прогоне, упавшем в середине.
    Завершение прогона меняет статус — и резерв перестаёт учитываться сам.
    """
    stmt = (
        select(func.coalesce(func.sum(UnitsLedger.units_estimated), 0))
        .join(Run, Run.id == UnitsLedger.run_id)
        .where(
            UnitsLedger.kind == LedgerKind.RESERVE,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    total: int | None = (await session.execute(stmt)).scalar_one()
    return total or 0


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
