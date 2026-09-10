"""Реапер зависших прогонов: строка в `running`, которую никто не завершит.

Прогон, убитый на середине (SIGKILL воркера, деплой, OOM), остаётся в `running`
навсегда: его резерв units продолжает занимать квоту, а оператор видит
«идёт» у того, что не идёт.

Паттерн взят из CRM агентства (`article_generation/run_reaper.py`,
SEOCRMLB-473) — там это ловили на проде дважды: генерация висела пятые сутки,
а один прогон keyword-базы финализировали руками через SQL. Перенесены приёмы,
не код:

1. **Мёртвого от медленного отличаем по возрасту, без heartbeat.** Живой прогон
   физически не идёт дольше своего таймаута, значит признак смерти — возраст.
   Поля `last_heartbeat` и миграции под него не нужно.
2. **Анкер — `coalesce(started_at, created_at)`.** Строка, которую успели
   перевести в `running`, но не проставить время старта, иначе не подпадает ни
   под одно условие и висит вечно — ровно то, от чего пишется реапер.
3. **`queued` судим мягче**: такая строка законно ждёт очереди.
4. **Guarded UPDATE** по всё ещё активному статусу: гонка двух реаперов и
   гонка с честно финишировавшим прогоном не перепишут терминальный статус.
5. **Причина — в строку прогона, а не в лог**: оператор должен понять из
   карточки, что случилось и что делать.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.storage._enums import RunStatus
from ahrefs_cases.storage.models.run import Run

logger = logging.getLogger(__name__)

REAP_BATCH_LIMIT = 50
"""Сколько строк добивать за проход. Не ручка: активных прогонов единицы,
пачка нужна лишь на хвост, накопившийся за месяцы."""


def _running_reason(threshold_sec: int) -> str:
    return (
        f"прогон простоял в running дольше {threshold_sec} с — исполнитель умер, "
        "не отметив завершение. Закрыт реапером: резерв units освобождён, "
        "уже собранные данные сохранены, запустите прогон заново — "
        "он догрузит только недостающее."
    )


def _queued_reason(threshold_sec: int) -> str:
    return (
        f"прогон простоял в очереди дольше {threshold_sec} с — задачу никто не "
        "подхватил (упала постановка в очередь либо очередь потеряна). "
        "Закрыт реапером, резерв units освобождён."
    )


async def reap_stale_runs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = REAP_BATCH_LIMIT,
) -> list[int]:
    """Закрыть зависшие прогоны. Возвращает id закрытых."""
    moment = now or datetime.now(UTC)
    running_after = config.ahrefs.run_stale_sec
    queued_after = config.ahrefs.run_queued_stale_sec

    stale = await _stale_runs(
        session,
        running_before=moment - timedelta(seconds=running_after),
        queued_before=moment - timedelta(seconds=queued_after),
        limit=limit,
    )
    reaped: list[int] = []
    for run_id, status in stale:
        reason = (
            _running_reason(running_after)
            if status is RunStatus.RUNNING
            else _queued_reason(queued_after)
        )
        result = await session.execute(
            update(Run)
            .where(
                Run.id == run_id,
                # Условие на прежний статус и есть идемпотентность: прогон,
                # успевший финишировать между выборкой и апдейтом, свой
                # результат сохраняет.
                Run.status == status,
            )
            .values(status=RunStatus.FAILED, finished_at=moment, error=reason)
        )
        # `rowcount` живёт на `CursorResult`, а `session.execute` типизирован
        # как `Result`: приведение вместо `type: ignore` — так видно, что
        # именно мы утверждаем, и mypy проверит остальное.
        if (cast("CursorResult[Any]", result).rowcount or 0) > 0:
            reaped.append(run_id)

    if reaped:
        logger.warning(
            "collect_runs_reaped",
            extra={"run_ids": reaped, "running_after_sec": running_after},
        )
    return reaped


async def _stale_runs(
    session: AsyncSession,
    *,
    running_before: datetime,
    queued_before: datetime,
    limit: int,
) -> list[tuple[int, RunStatus]]:
    """Id зависших прогонов с их статусом: пороги у `running` и `queued` разные."""
    anchor = func.coalesce(Run.started_at, Run.created_at)
    stmt = (
        select(Run.id, Run.status)
        .where(
            or_(
                (Run.status == RunStatus.RUNNING) & (anchor < running_before),
                (Run.status == RunStatus.QUEUED) & (Run.created_at < queued_before),
            )
        )
        .order_by(Run.id)
        .limit(limit)
    )
    return [(int(run_id), status) for run_id, status in (await session.execute(stmt)).all()]
