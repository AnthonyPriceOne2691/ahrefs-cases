"""Реапер прогонов: чью задачу считать мёртвой и что делать с её прогоном.

Прогон, убитый выкаткой посреди работы, оставался `running` навсегда, а замок
«один активный прогон» отвечал 409 на каждую кнопку — выход был только из
консоли. Реапер-процесс с тикером закрывает такие прогоны с причиной; здесь —
правило, по которому он решает, и то, чего он не трогает.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rq.job import JobStatus
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api import security
from ahrefs_cases.storage import RunStatus, UserGroup
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers.reaper import (
    GRACE,
    JobState,
    Liveness,
    close_orphans,
    judge,
    status_text,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (JobState(found=True, status="queued"), Liveness.ALIVE),
        (JobState(found=True, status="started", worker_alive=True), Liveness.ALIVE),
        (JobState(found=True, status="started", worker_alive=False), Liveness.DEAD),
        (JobState(found=False), Liveness.DEAD),
        (JobState(found=True, status="failed", error="KeyError: 'x'"), Liveness.DEAD),
        (JobState(found=True, status="finished"), Liveness.DEAD),
    ],
)
def test_judge(state: JobState, expected: Liveness) -> None:
    verdict, why = judge(state)
    assert verdict is expected
    assert bool(why) is (expected is Liveness.DEAD), "мёртвая задача обязана назвать причину"


@pytest.mark.parametrize("status", list(JobStatus))
def test_status_from_rq_reaches_the_judge_as_its_value(status: JobStatus) -> None:
    """Перевод статуса из RQ — значением: `str()` давал «JobStatus.QUEUED».

    С ним ждущая в очереди задача не узнавалась, и реапер закрывал прогон,
    который просто ждал воркера. Тесты `judge` этого не видели: они подают
    готовые строки и минуют перевод.
    """
    assert status_text(status) == status.value
    if status in {JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED}:
        assert judge(JobState(found=True, status=status_text(status)))[0] is Liveness.ALIVE


def test_started_job_of_a_vanished_worker_names_the_deploy() -> None:
    """Статус «started» после SIGKILL остаётся навсегда — судит живость воркера."""
    _, why = judge(JobState(found=True, status="started", worker_alive=False))
    assert "выкатка" in why


def test_failed_job_carries_its_own_error() -> None:
    """Упавшая задача — не «воркер умер»: причина берётся из самой задачи."""
    _, why = judge(JobState(found=True, status="failed", error="ZeroDivisionError: деление"))
    assert "ZeroDivisionError" in why


async def _run(session: AsyncSession, author: int, *, key: str, age: timedelta) -> Run:
    run = Run(
        started_by=author,
        status=RunStatus.RUNNING,
        projects_total=3,
        params_snapshot={"job": key} if key else {},
        created_at=NOW - age,
    )
    session.add(run)
    await session.flush()
    return run


async def test_close_orphans_touches_only_dead_keyed_runs(db_session: AsyncSession) -> None:
    user = User(
        email="reaper@test.local",
        full_name="Реапер",
        password_hash=security.hash_password("очень-длинный-пароль"),
        group=UserGroup.USER,
    )
    db_session.add(user)
    await db_session.flush()
    old = GRACE + timedelta(minutes=5)
    dead = await _run(db_session, user.id, key="run-dead", age=old)
    console = await _run(db_session, user.id, key="", age=old)
    unsure = await _run(db_session, user.id, key="run-unsure", age=old)
    fresh = await _run(db_session, user.id, key="run-dead-too", age=timedelta(seconds=10))
    answers = {
        "run-dead": (Liveness.DEAD, "воркер исчез"),
        "run-dead-too": (Liveness.DEAD, "воркер исчез"),
        "run-unsure": (Liveness.UNKNOWN, ""),
    }

    closed = await close_orphans(db_session, answers.__getitem__, NOW)

    assert closed == [dead.id]
    for run in (dead, console, unsure, fresh):
        await db_session.refresh(run)
    assert dead.status is RunStatus.FAILED
    assert dead.error.startswith("воркер исчез.")
    assert "запустите прогон заново" in dead.error
    # Консольный прогон идёт без очереди — «задачи нет» его не касается.
    assert console.status is RunStatus.RUNNING
    # «Redis не ответил» — не «мертва»: второй платный заход хуже ожидания.
    assert unsure.status is RunStatus.RUNNING
    # Моложе льготной минуты не судим: строка пишется раньше, чем задача встаёт.
    assert fresh.status is RunStatus.RUNNING
