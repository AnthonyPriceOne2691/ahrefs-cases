"""Реапер прогонов — отдельным процессом с тикером.

Зачем отдельно. Замок «один активный прогон» в API отказывает, пока есть
`queued` или `running`. Прогон, чью задачу убили — выкатка пересоздала воркер,
кончилась память, — остаётся `running` навсегда: API отвечает 409, а прежний
реапер (`collect.run_reaper`) вызывался только в начале нового сбора внутри
воркера, то есть никогда — новый сбор не начинался. Воркер свою смерть не
разберёт, API — не место для фоновой работы; значит, третий процесс. Приём —
из соседнего сервиса на той же машине (24.09.2026).

Каждую минуту:

1. прежний реап по возрасту — страховка для прогонов без ключа задачи
   (консольные и старше этого поля);
2. прогоны с ключом задачи (поставленные через очередь) проверяются по RQ.
   Задача жива, если ждёт в очереди или её держит воркер, чей
   `rq:worker:<имя>` ещё есть в Redis: ключ исчезает вместе с процессом, а
   статус задачи после SIGKILL навсегда остаётся «started». Мертва — если
   задачи нет, её взял исчезнувший воркер или она кончилась, а прогон не
   закрыт. «Redis не ответил» — не «мертва»: такой прогон не трогаем.

Мёртвую закрываем `failed` с причиной, охраняемым UPDATE по прежнему статусу.
Продолжения за человека нет: повторный запуск и так дешёвый — закрытые месяцы
второй раз не покупаются, а собранное до последнего чекпойнта сохранено.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from redis import Redis
from redis.exceptions import RedisError
from rq import Worker
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.run_reaper import reap_stale_runs
from ahrefs_cases.logs import setup_logging
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.session import get_sessionmaker

logger = logging.getLogger(__name__)

TICK_SEC = 60
GRACE = timedelta(seconds=60)
"""Строка прогона пишется раньше, чем задача встаёт в очередь: моложе этого —
не судим, иначе поймали бы прогон в промежутке между двумя шагами API."""

BEAT = Path("/tmp/ahrefs-cases-reaper.beat")  # noqa: S108 — отметка внутри своего контейнера
BEAT_STALE_SEC = 3 * TICK_SEC

TAIL = (
    "Закрыт реапером: резерв units освобождён, собранное до последнего чекпойнта "
    "сохранено; запустите прогон заново — он догрузит только недостающее."
)

_WAITING = frozenset({JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED})


class Liveness(StrEnum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class JobState:
    """Что известно о задаче из очереди. Отдельно от RQ — решение проверяется тестом."""

    found: bool
    status: str = ""
    worker_alive: bool = False
    error: str = ""


def judge(state: JobState) -> tuple[Liveness, str]:
    """Жива ли задача прогона, и если нет — почему, словами для строки прогона."""
    if not state.found:
        return Liveness.DEAD, "задачи прогона нет в очереди — она потеряна"
    if state.status in _WAITING:
        return Liveness.ALIVE, ""
    if state.status == JobStatus.STARTED:
        if state.worker_alive:
            return Liveness.ALIVE, ""
        return (
            Liveness.DEAD,
            "воркер, взявший задачу, исчез — перезапуск контейнера или выкатка посреди прогона",
        )
    if state.status == JobStatus.FAILED:
        return Liveness.DEAD, (
            f"задача упала: {state.error}" if state.error else "задача упала без записанной причины"
        )
    return Liveness.DEAD, f"задача кончилась ({state.status}), а прогон так и не закрыт"


def status_text(status: JobStatus | None) -> str:
    """Статус задачи строкой — значением, а не `str()`.

    `JobStatus` наследует от `str`, но `str(JobStatus.QUEUED)` в Python 3.12 —
    это `"JobStatus.QUEUED"`, а не `"queued"`. Через `str()` ни одно сравнение
    не срабатывало, и реапер закрывал как мёртвый прогон, чья задача законно
    ждала в очереди (сквозная проверка на боевых образах, 24.09.2026).
    """
    return status.value if status is not None else ""


def job_state(connection: Redis, key: str) -> JobState:
    """Прочитать задачу из очереди. Ошибки Redis — наверх: это «не знаю», а не «мертва»."""
    try:
        job = Job.fetch(key, connection=connection)
    except NoSuchJobError:
        return JobState(found=False)
    status = job.get_status(refresh=False)
    name = job.worker_name
    alive = bool(name) and bool(connection.exists(f"{Worker.redis_worker_namespace_prefix}{name}"))
    error = ""
    if status == JobStatus.FAILED:
        result = job.latest_result()
        text = (getattr(result, "exc_string", "") or "").strip()
        error = text.splitlines()[-1][:300] if text else ""
    return JobState(found=True, status=status_text(status), worker_alive=alive, error=error)


async def close_orphans(
    session: AsyncSession, ask: Callable[[str], tuple[Liveness, str]], now: datetime
) -> list[int]:
    """Закрыть прогоны, чья задача мертва. Без ключа и в сомнении — не трогать."""
    stmt = select(Run.id, Run.status, Run.params_snapshot).where(
        Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]), Run.created_at < now - GRACE
    )
    closed: list[int] = []
    for run_id, status, snapshot in (await session.execute(stmt)).all():
        key = (snapshot or {}).get("job")
        if not key:
            continue
        verdict, why = ask(str(key))
        if verdict is not Liveness.DEAD:
            continue
        result = await session.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == status)
            .values(status=RunStatus.FAILED, finished_at=now, error=f"{why}. {TAIL}")
        )
        if (cast("CursorResult[Any]", result).rowcount or 0) > 0:
            closed.append(run_id)
    return closed


def _asker(connection: Redis) -> Callable[[str], tuple[Liveness, str]]:
    def ask(key: str) -> tuple[Liveness, str]:
        try:
            return judge(job_state(connection, key))
        except RedisError as exc:
            logger.warning("reaper_queue_unreachable", extra={"job": key, "error": str(exc)})
            return Liveness.UNKNOWN, ""

    return ask


async def sweep(connection: Redis) -> list[int]:
    """Один проход: сначала по возрасту, потом по живости задачи."""
    now = datetime.now(UTC)
    async with get_sessionmaker()() as session:
        stale = await reap_stale_runs(session, now=now)
        orphans = await close_orphans(session, _asker(connection), now)
        await session.commit()
    if orphans:
        logger.warning("runs_closed_by_reaper", extra={"run_ids": orphans})
    return [*stale, *orphans]


async def _forever() -> None:
    connection = Redis.from_url(config.storage.redis_url)
    while True:
        try:
            await sweep(connection)
        except Exception as exc:
            # Проход упал — следующий через минуту; отметка о жизни не пишется,
            # и проверка здоровья покажет, что реапер ослеп, а не молчит довольный.
            logger.exception("reaper_sweep_failed", extra={"error": str(exc)})
        else:
            await asyncio.to_thread(_beat)
        await asyncio.sleep(TICK_SEC)


def _beat() -> None:
    BEAT.write_text(str(time.time()))


def check() -> int:
    """Проверка здоровья: отметка последнего удачного прохода свежая."""
    try:
        age = time.time() - float(BEAT.read_text())
    except (OSError, ValueError) as exc:
        logger.warning("reaper_beat_missing", extra={"error": str(exc)})
        print(f"нет отметки реапера: {exc}", file=sys.stderr)
        return 1
    if age > BEAT_STALE_SEC:
        logger.warning("reaper_beat_stale", extra={"age_sec": int(age)})
        print(f"реапер не проходил {int(age)} с при пределе {BEAT_STALE_SEC} с", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check()
    setup_logging()
    logger.info("reaper_started", extra={"tick_sec": TICK_SEC})
    asyncio.run(_forever())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
