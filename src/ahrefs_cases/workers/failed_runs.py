"""Упавшие прогоны — в Telegram, каждый ровно один раз.

Прогон закрывается `failed` в пяти местах: журнал сбора, задачи воркера, цикл
по файлу и два реапера. Алерт, вписанный в каждое, забыли бы в шестом, поэтому
объявляет реапер: раз в тик берёт упавшие после отметки и двигает её за каждым
доставленным. Отметка — время закрытия и номер прогона (у двух прогонов время
может совпасть) — живёт в Redis и переживает перезапуск контейнера. Её нет
(первый запуск, очищенный Redis) — ставится на «сейчас»: история новостью не
считается. Telegram не принял — отметка стоит, повтор в следующий тик.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol

from redis import Redis
from sqlalchemy import DateTime, Integer, func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.run import Run

logger = logging.getLogger(__name__)

MARK_KEY = "ahrefs-cases:alerts:failed-runs"
BATCH = 10
"""За тик — не больше десяти: пачка упавших разом не забивает чат одним залпом."""

_REASON_LIMIT = 500


class Mark(Protocol):
    def read(self) -> tuple[datetime, int] | None: ...

    def write(self, at: datetime, run_id: int) -> None: ...


class RedisMark:
    """Отметка «объявлено до» в Redis: `<время ISO>|<номер прогона>`."""

    def __init__(self, connection: Redis) -> None:
        self._connection = connection

    def read(self) -> tuple[datetime, int] | None:
        raw = self._connection.get(MARK_KEY)
        if raw is None:
            return None
        at, _, run_id = (raw.decode() if isinstance(raw, bytes) else str(raw)).partition("|")
        return datetime.fromisoformat(at), int(run_id or 0)

    def write(self, at: datetime, run_id: int) -> None:
        self._connection.set(MARK_KEY, f"{at.isoformat()}|{run_id}")


def failure_text(run: Run) -> str:
    stage = run.params_snapshot.get("stage")
    where = f" (ступень {stage})" if stage else ""
    reason = (run.error or "").strip() or "причина не записана"
    return f"Ahrefs Cases: прогон №{run.id}{where} упал — {reason[:_REASON_LIMIT]}"


def _after(mark: tuple[datetime, int]) -> ColumnElement[Any]:
    """Отметка — строкой сравнения «время, номер»: тип времени — как у колонки."""
    return tuple_(literal(mark[0], DateTime(timezone=True)), literal(mark[1], Integer))


async def announce_failed_runs(
    session: AsyncSession,
    mark: Mark,
    send: Callable[[str], Awaitable[bool]],
    now: datetime,
) -> list[int]:
    """Объявить упавшие после отметки; вернуть номера доставленных."""
    since = mark.read()
    if since is None:
        mark.write(now, 0)
        return []
    closed = func.coalesce(Run.finished_at, Run.created_at)
    runs = (
        await session.execute(
            select(Run, closed)
            .where(Run.status == RunStatus.FAILED, tuple_(closed, Run.id) > _after(since))
            .order_by(closed, Run.id)
            .limit(BATCH)
        )
    ).all()
    delivered: list[int] = []
    for run, at in runs:
        if not await send(failure_text(run)):
            break
        mark.write(at, run.id)
        delivered.append(run.id)
    if delivered:
        logger.info("failed_runs_announced", extra={"run_ids": delivered})
    return delivered
