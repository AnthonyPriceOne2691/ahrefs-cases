"""Расход units: строка журнала на каждый запрос к провайдеру.

Ф2а ведёт **факт**: сколько запросов сделано и во что они обошлись. Смета,
резервы и мягкий стоп — Ф2б; они опираются на этот же журнал, поэтому он должен
существовать раньше и заполняться одинаково в обоих режимах.

В fixture-режиме units условные, но считаются моделью стоимости живого API
(`EndpointSpec.estimate_units`). Ноль здесь означал бы, что экран расхода и
смета разрабатываются на нулях и проверяются впервые в Ф7 — на деньгах заказчика.

**Условные units — не расход.** Отличить их от настоящих можно только по
прогону, и это правило живёт здесь одно (`_live_run`): вычет из остатка
(`live_spend_since`) и экран расхода (`spend_summary`) спрашивают его, а не
суммируют журнал сами. До 24.09.2026 экран суммировал журнал в роутере, и
«потрачено» складывало условные units с настоящими (Z38).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.provider import HistoryResult
from ahrefs_cases.storage._enums import LedgerKind, RunStatus
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

logger = logging.getLogger(__name__)

_LIVE_PROVIDER = "live"
"""Значение `params_snapshot['provider']` у прогона, который ходил в настоящий
Ahrefs. Строкой, а не enum'ом: снимок параметров — это JSON, записанный в тот
день, и он обязан читаться даже если имена режимов потом поменяются."""

_HUNDRED = 100


def _live_run() -> ColumnElement[bool]:
    """Прогон ходил в настоящий Ahrefs — единственное место этого правила.

    Режим — свойство прогона, а не строки журнала: снимок параметров пишется
    при открытии прогона (`run_journal.open_run`). Прогон без режима в снимке
    (следы старых тестов) живым не считается: настоящим расход признаётся
    только тогда, когда журнал это знает.
    """
    rule: ColumnElement[bool] = Run.params_snapshot["provider"].astext == _LIVE_PROVIDER
    return rule


async def live_runs(session: AsyncSession, run_ids: Collection[int]) -> frozenset[int]:
    """Какие из прогонов живые — тем же правилом, что считает «потрачено».

    Журнал прогонов помечает условные units по этому ответу: спроси он режим
    сам, у правила появилась бы вторая копия, и журнал с экраном расхода
    разошлись бы на первом же новом режиме (L208).
    """
    if not run_ids:
        return frozenset()
    rows = await session.execute(select(Run.id).where(Run.id.in_(list(run_ids)), _live_run()))
    return frozenset(rows.scalars())


def _spent(*columns: ColumnElement[Any]) -> Select[Any]:
    """Вопрос к строкам расхода — каркас каждого «сколько ушло» и «за что платили»."""
    return select(*columns).where(UnitsLedger.kind == LedgerKind.SPENT)


def _live(stmt: Select[Any]) -> Select[Any]:
    """Тот же вопрос, но только к живым прогонам."""
    return stmt.join(Run, Run.id == UnitsLedger.run_id).where(_live_run())


def _units() -> ColumnElement[Any]:
    """Сумма `units_actual`; пустая сумма — ноль, а не `NULL`."""
    return func.coalesce(func.sum(UnitsLedger.units_actual), 0)


async def _total(session: AsyncSession, stmt: Select[Any]) -> int:
    """Одно число из запроса; пустой ответ — ноль, а не `None`."""
    total: int | None = (await session.execute(stmt)).scalar_one()
    return total or 0


def estimate_drift_pct(result: HistoryResult) -> float | None:
    """На сколько процентов факт разошёлся со сметой. `None` — считать не по чему.

    Возвращает число, а не пишет в лог: проверять логику по логам — значит
    зависеть от того, как их перехватывает раннер (поймано тестом, который
    проходил в одиночку и падал в общем прогоне). Лог остаётся, но он
    следствие, а не результат.

    Зачем вообще: модель стоимости оказалась неверной в разы — разведка Ф7
    показала `estimated=693` там, где мы обещали 50. Такое расхождение обязано
    быть слышно в первом же прогоне, а не в счёте Ahrefs в конце месяца.
    """
    if result.units_estimated <= 0 or result.units_actual <= 0:
        return None
    return abs(result.units_actual - result.units_estimated) / result.units_estimated * 100


def _warn_if_estimate_missed(result: HistoryResult) -> None:
    """Записать расхождение в лог, если оно выше допустимого."""
    drift = estimate_drift_pct(result)
    if drift is None or drift <= config.ahrefs.estimate_tolerance_pct:
        return
    logger.warning(
        "ahrefs_estimate_missed",
        extra={
            "endpoint": result.endpoint,
            "target": result.target,
            "estimated": result.units_estimated,
            "actual": result.units_actual,
            "drift_pct": round(drift, 1),
        },
    )


async def record_spend(session: AsyncSession, run_id: int, result: HistoryResult) -> None:
    """Записать стоимость одного ответа провайдера."""
    _warn_if_estimate_missed(result)
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


async def live_spend_since(session: AsyncSession, moment: datetime) -> int:
    """Сколько units потратили **живые** прогоны с этого момента, по журналу.

    Живые — по снимку параметров прогона (`_live_run`), а не по всем строкам:
    fixture-прогоны считают условные units по той же формуле, и вычитать их из
    настоящего остатка Ahrefs значило бы уменьшать чужое число своей игрой.

    Один запрос на весь проект: его же зовёт `scripts/probe_next_day.py`, когда
    сверяет счётчик Ahrefs с нашим журналом. Две копии разошлись бы ровно тогда,
    когда сверка начнёт что-то значить.
    """
    return await _total(session, _live(_spent(_units())).where(UnitsLedger.created_at >= moment))


async def uncounted_spend(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Расход, которого счётчик Ahrefs ещё не видит.

    **Зачем.** Остаток из API — величина вчерашняя: замер 13.09.2026 показал,
    что 50 units, потраченные минутами раньше, в `units_usage_api_key` не
    отражены, а за сутки счётчик сдвигается. Резерв прогона эту дыру не
    закрывает — он живёт только пока прогон в статусе `queued`/`running`
    (`reserved_units`), то есть снимается раньше, чем счётчик обновляется.
    В промежутке остаток завышен ровно на стоимость последнего прогона.

    **Ошибка намеренно односторонняя.** Часть этого расхода счётчик может уже
    учитывать — тогда мы вычтем её дважды и откажем лишний раз. Цена обратной
    ошибки — прогон, оборванный на середине с половиной собранных проектов.

    `now` параметром, а не `datetime.now()` внутри: иначе поведение проверяется
    только подкруткой системных часов.
    """
    moment = (now or datetime.now(UTC)) - timedelta(hours=config.ahrefs.units_counter_lag_hours)
    return await live_spend_since(session, moment)


@dataclass(frozen=True, slots=True)
class SpendSummary:
    """Расход по журналу, разделённый правилом «условные units — не расход»."""

    live: int
    """Настоящий расход: строки `SPENT` живых прогонов."""

    conditional: int
    """Всё остальное в журнале: столько насчитали прогоны без живого ключа по
    формуле живого API. Не расход — но и не ноль: экран называет их отдельно,
    иначе «потрачено 0» спорило бы с журналом прогонов, где у каждого есть факт."""

    live_domains: int
    """Сколько доменов оплачено живьём: различные `target` тех же строк, что
    дают `live`. Числитель и знаменатель берутся из одного журнала одним
    правилом, а журнал удаление проектов не трогает — стоимость на сто не
    меняется оттого, что проект убрали из списка."""

    def per_hundred(self) -> int | None:
        """«Стоимость запуска на 100 URL» по факту — метрика успеха из ТЗ.

        Живые units на оплаченные живьём домены. Прежний знаменатель (все
        проекты базы) разбавлял стоимость проектами, которые в Ahrefs не
        ходили, и рос бы от одного удаления проекта. `None` — живого расхода
        нет, и ноль здесь читался бы как «бесплатно» (L191).
        """
        if not self.live or not self.live_domains:
            return None
        return round(self.live / self.live_domains * _HUNDRED)


async def spend_summary(session: AsyncSession) -> SpendSummary:
    """Что показать на экране расхода — по тому же правилу, что вычет из остатка.

    Одним запросом, а не тремя: экран опрашивают и во время живого прогона, а
    каждый запрос в `READ COMMITTED` видит свой снимок. Строка, записанная между
    суммой живых и суммой всех, попала бы в разницу — и экран чисто живого
    журнала на миг показал бы «условные units» прогона, который в Ahrefs ходил.
    """
    live = _live_run()
    stmt = _spent(
        func.coalesce(func.sum(UnitsLedger.units_actual).filter(live), 0),
        _units(),
        func.count(func.distinct(UnitsLedger.target)).filter(live),
    ).outerjoin(Run, Run.id == UnitsLedger.run_id)
    spent, everything, domains = (await session.execute(stmt)).one()
    return SpendSummary(live=spent, conditional=everything - spent, live_domains=domains)


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

    Режим прогона здесь не спрашивается: у одного прогона он один, и его цена
    не смешивает условные units с настоящими.
    """
    return await _total(session, _spent(_units()).where(UnitsLedger.run_id == run_id))
