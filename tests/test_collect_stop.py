"""Упавший прогон перестаёт покупать (Z52, деньги).

Примеры приёмки поставки `collect-stops-on-failure`: M96 (после сбоя записи новых запросов нет), M97 (ни одна
задача сбора не переживает прогон), M98 (смерть процесса: записанное остаётся, реапер закрывает прогон,
повторный сбор покупает только незаписанное).

M96 и M97 — в процессе теста, на откатываемой транзакции. M98 — настоящим SIGKILL дочернего процесса
(`tests/collect_child.py`): он пишет своими соединениями, поэтому строки теста закоммичены, и тест убирает за
собой сам (`tests/cli_world.own_world`, уроки L51, L80).
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tests.cli_world import own_world

from ahrefs_cases import config
from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.run_reaper import reap_stale_runs
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import RunStatus
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.session import get_sessionmaker

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)
CHILD = Path(__file__).resolve().parent / "collect_child.py"
IN_FLIGHT = "в сети: "
"""Строка дочернего сбора о висящем запросе — `tests/collect_child.py`."""


async def _load(session: AsyncSession, domains: list[str]) -> None:
    rows = "\n".join(
        f"{domain},2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for domain in domains
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))


class SlowFixture(AhrefsFixture):
    """Фикстура, считающая обращения; каждый ответ идёт «по сети» — с паузой.

    Без паузы ответ фикстуры готов сразу, и вся очередь успевала бы купиться ещё до
    того, как сбой дойдёт до цикла: тест не отличил бы остановку от того, что
    останавливать было уже нечего.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append(request.target)
        await asyncio.sleep(0.01)
        return await super().fetch_history(spec, request)


@dataclass
class Failure:
    """Сбор с упавшей записью: провайдер и сколько запросов он получил к мигу сбоя."""

    provider: SlowFixture = field(default_factory=SlowFixture)
    calls_at_failure: int = -1


@pytest.fixture
def failure(monkeypatch: pytest.MonkeyPatch) -> Failure:
    """Параллель 3; запись результата падает на третьем проекте."""
    from ahrefs_cases.collect import run_journal

    real = run_journal.store_history
    found = Failure()
    stores = 0

    async def store(*args: object, **kwargs: object) -> int:
        nonlocal stores
        stores += 1
        if stores == 3:
            found.calls_at_failure = len(found.provider.calls)
            message = "база отвалилась на третьей записи"
            raise RuntimeError(message)
        return await real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(config.ahrefs, "max_parallel", 3)
    monkeypatch.setattr(run_journal, "store_history", store)
    return found


TASK = "execute_tasks.<locals>.one"
"""Имя корутины задачи сбора (`collect/execute.py`). Проверка «задач не осталось» опирается на
него, поэтому сначала убеждается, что задачи с этим именем вообще бывают (`test_task_name_is_real`):
фильтр, не находящий ничего, зеленел бы при любом коде."""


def _collect_tasks() -> list[asyncio.Task[object]]:
    """Незавершённые задачи сбора в цикле событий теста."""
    return [
        task
        for task in asyncio.all_tasks()
        if getattr(task.get_coro(), "__qualname__", "") == TASK and not task.done()
    ]


async def test_failed_run_starts_no_new_purchases(
    db_session: AsyncSession, failure: Failure
) -> None:
    """M96: после сбоя записи провайдер не получает ни одного нового запроса.

    До правки задачи `as_completed` оставались после выхода исключения и докупали
    остаток списка — ответы, которые уже никто не запишет.
    """
    await _load(db_session, [f"stop{index:02d}.example.com" for index in range(12)])

    with pytest.raises(RuntimeError, match="третьей записи"):
        await collect_all(db_session, failure.provider, now=NOW)
    await asyncio.sleep(0.3)

    assert len(failure.provider.calls) == failure.calls_at_failure


async def test_no_collect_task_outlives_the_failed_run(
    db_session: AsyncSession, failure: Failure, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M97: когда исключение вышло из цикла задач, задач сбора в цикле событий не осталось.

    Смотрится на входе в `_fail_run`, а не после `collect_all`: откат сессии там уступает
    циклу событий, и отменённые, но не дождавшиеся задачи успевали бы закончиться сами —
    проверка после сбора не отличила бы «дождался» от «повезло».
    """
    from ahrefs_cases.collect import runner

    real = runner._fail_run
    left: list[list[asyncio.Task[object]]] = []

    async def fail_run(*args: object, **kwargs: object) -> None:
        left.append(_collect_tasks())
        await real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(runner, "_fail_run", fail_run)
    await _load(db_session, [f"left{index:02d}.example.com" for index in range(12)])

    with pytest.raises(RuntimeError, match="третьей записи"):
        await collect_all(db_session, failure.provider, now=NOW)

    assert left == [[]]


async def test_task_name_is_real(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Опора M97: посреди сбора задачи с именем `TASK` видны — фильтр ловит настоящие задачи."""
    seen: list[int] = []

    class Peeking(SlowFixture):
        async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
            seen.append(len(_collect_tasks()))
            return await super().fetch_history(spec, request)

    monkeypatch.setattr(config.ahrefs, "max_parallel", 3)
    await _load(db_session, [f"peek{index}.example.com" for index in range(4)])

    await collect_all(db_session, Peeking(), now=NOW)

    assert seen and min(seen) >= 1


CRASH_DOMAINS = [f"crash{index}.example.com" for index in range(4)]
CRASH_RULESET = "0.0.0-collect-crash"


async def _stored_domains() -> set[str]:
    async with get_sessionmaker()() as session:
        stmt = (
            select(Project.domain)
            .join(MetricPoint, MetricPoint.project_id == Project.id)
            .where(Project.domain.in_(CRASH_DOMAINS))
            .distinct()
        )
        return set((await session.execute(stmt)).scalars().all())


async def _kill_mid_request() -> str:
    """Запустить сбор в дочернем процессе и убить его SIGKILL, пока третий запрос «в сети».

    Убивает, когда дочерний процесс назвал висящий запрос и два первых домена уже закоммичены:
    семафор отпускает третий запрос раньше, чем цикл записывает второй ответ.
    """
    env = os.environ | {
        "DATABASE_URL": config.storage.database_url,
        "AHREFS_PROVIDER": "fixture",
        "COLLECT_MAX_PARALLEL": "1",
        "COLLECT_CHECKPOINT_EVERY": "1",
    }
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        str(CHILD),
        ",".join(CRASH_DOMAINS),
        env=env,
        stdout=asyncio.subprocess.PIPE,
    )
    assert child.stdout is not None
    try:
        line = (await asyncio.wait_for(child.stdout.readline(), timeout=60)).decode()
        assert line.startswith(IN_FLIGHT), f"дочерний сбор не дошёл до третьего запроса: {line!r}"
        for _ in range(300):
            if len(await _stored_domains()) == 2:
                break
            await asyncio.sleep(0.1)
        assert child.returncode is None, "дочерний сбор кончился сам, до SIGKILL"
    finally:
        if child.returncode is None:
            child.kill()
        await child.wait()
    return line.removeprefix(IN_FLIGHT).strip()


async def test_killed_collect_keeps_what_it_wrote_and_buys_only_the_rest(
    migrated_db: None,
) -> None:
    """M98: SIGKILL посреди запроса — записанное остаётся, реапер закрывает, остаток докупается.

    Висевший запрос теряется: на живом ключе его ответ мог быть оплачен, и повторный сбор
    покупает его заново — граница, названная в Z52, а не дефект.
    """
    async with own_world(ruleset=CRASH_RULESET, domains=CRASH_DOMAINS):
        async with get_sessionmaker()() as session:
            last_run = int(await session.scalar(select(func.max(Run.id))) or 0)
            await _load(session, CRASH_DOMAINS)
            await session.commit()

        hanging = await _kill_mid_request()

        # Порядок запросов задаёт план, а не список: сверяется не «какие», а «сколько и кто остался».
        stored = await _stored_domains()
        assert (len(stored), hanging in stored) == (2, False)
        async with get_sessionmaker()() as session:
            killed = (
                (await session.execute(select(Run).where(Run.id > last_run).order_by(Run.id)))
                .scalars()
                .one()
            )
            assert killed.status is RunStatus.RUNNING
            stale = datetime.now(UTC) - timedelta(seconds=config.ahrefs.run_stale_sec + 60)
            await session.execute(update(Run).where(Run.id == killed.id).values(started_at=stale))
            await session.commit()
            assert killed.id in await reap_stale_runs(session)
            await session.commit()
            await session.refresh(killed)
            assert killed.status is RunStatus.FAILED

            again = SlowFixture()
            await collect_all(session, again, now=NOW, only=CRASH_DOMAINS)
        assert set(again.calls) == set(CRASH_DOMAINS) - stored
