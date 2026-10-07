"""Консоль под тем же замком прогона, что кнопка (Z52). Примеры приёмки: M68–M70.

Кнопка ставит прогон под замком постановки: `hold_start`, «активных нет» и строка
прогона — одной транзакцией (`api/routers/runs.py::_enqueue`). Платящие команды
консоли открывали прогон в обход: при идущем прогоне кнопкой консоль запускала второй,
и оба покупали одни и те же ряды.

Строки пишутся коммитом и убираются тестом сам — почему так, сказано в `tests/cli_world.py`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.cli_world import own_world

from ahrefs_cases.cli import collect_commands
from ahrefs_cases.collect import runner
from ahrefs_cases.collect.run_journal import SYSTEM_USER_EMAIL, open_run
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage._enums import Group, MetricSource, RunStatus
from ahrefs_cases.storage.locks import hold_start
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict
from ahrefs_cases.storage.session import get_sessionmaker

DOMAIN = "lock.example"
EMAIL = "lock-button@example.com"
RULESET = "0.0.0-cli-lock"
EXIT_BUSY = 5


@pytest.fixture
async def project(migrated_db: None) -> AsyncIterator[int]:
    """Свой проект и свой человек у кнопки при своей действующей версии порогов."""
    async with own_world(ruleset=RULESET, domains=(DOMAIN,), emails=(EMAIL,)):
        async with get_sessionmaker()() as session:
            row = Project(
                domain=DOMAIN,
                period_start=date(2025, 1, 1),
                period_end=date(2026, 6, 1),
                niche="fintech",
                geo="US",
                service_type="seo",
                client="Acme",
                owner="i.petrov",
                publishable=True,
                notes="",
            )
            person = User(email=EMAIL, full_name="Кнопка", password_hash="-", group=UserGroup.USER)
            session.add_all([row, person])
            await session.commit()
            project_id = row.id
        yield project_id


async def _button_run(*, running: bool) -> int:
    """Прогон кнопкой: строка `running`, как её оставляет воркер посреди работы."""
    async with get_sessionmaker()() as session:
        author = await session.scalar(select(User.id).where(User.email == EMAIL))
        assert author is not None
        run = await open_run(session, started_by=author, projects_total=1, job_key="run-button")
        if running:
            run.status = RunStatus.RUNNING
        await session.commit()
        return run.id


async def _good_verdict(project_id: int) -> None:
    """«Хороший» по действующей версии — без него `case-data` до сбора не доходит."""
    async with get_sessionmaker()() as session:
        ruleset = await session.scalar(select(Ruleset.id).where(Ruleset.version == RULESET))
        assert ruleset is not None
        session.add(Verdict(project_id=project_id, ruleset_id=ruleset, group=Group.GOOD))
        await session.commit()


async def _everyone(
    _session: AsyncSession, projects: Sequence[Project], *, source: MetricSource
) -> list[int]:
    """Каждый — кандидат: шаг 2 доходит до сбора, не считая классификацию."""
    del source
    return [one.id for one in projects]


async def _last_run() -> int:
    async with get_sessionmaker()() as session:
        return int(await session.scalar(select(func.max(Run.id))) or 0)


async def _runs_after(run_id: int) -> list[tuple[int, RunStatus, str]]:
    """Прогоны, открытые после названного: номер, статус и почта автора."""
    async with get_sessionmaker()() as session:
        stmt = (
            select(Run.id, Run.status, User.email)
            .join(User, User.id == Run.started_by)
            .where(Run.id > run_id)
            .order_by(Run.id)
        )
        return [(one.id, one.status, one.email) for one in await session.execute(stmt)]


@pytest.fixture
def no_purchase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Консоль, отказавшая под замком, до провайдера не доходит: любой его вызов — падение."""

    def forbidden() -> object:
        message = "консоль при идущем прогоне не имеет права покупать"
        raise AssertionError(message)

    monkeypatch.setattr(runner, "build_provider", forbidden)


@pytest.mark.usefixtures("no_purchase")
async def test_console_refuses_while_a_run_is_active(
    project: int, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """M68: при идущем прогоне кнопкой все три платящие команды отказывают кодом 5."""
    await _good_verdict(project)
    before = await _last_run()
    busy = await _button_run(running=True)
    monkeypatch.setattr(collect_commands, "stage2_candidates", _everyone)

    codes = [
        await collect_commands._collect(only=[DOMAIN]),
        await collect_commands._stage2(only=[DOMAIN]),
        await collect_commands._case_data(only=[DOMAIN]),
    ]

    assert codes == [EXIT_BUSY, EXIT_BUSY, EXIT_BUSY]
    told = capsys.readouterr().err
    assert told.count(f"прогон {busy} ещё идёт (running); второй не запускается") == 3
    assert [one[0] for one in await _runs_after(before)] == [busy]


@pytest.mark.usefixtures("project", "no_purchase")
async def test_console_waits_for_the_start_lock_and_sees_the_new_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """M69: пока кнопка держит замок постановки, консоль ждёт; увидев открытую строку — отказывает."""
    before = await _last_run()
    async with get_sessionmaker()() as button:
        author = await button.scalar(select(User.id).where(User.email == EMAIL))
        assert author is not None
        await hold_start(button)
        run = await open_run(button, started_by=author, projects_total=1, job_key="run-button")
        opened = run.id
        console = asyncio.create_task(collect_commands._collect(only=[DOMAIN]))
        await asyncio.sleep(0.5)
        waited = not console.done()
        await button.commit()
    code = await asyncio.wait_for(console, timeout=10)

    assert waited, "консоль не ждала замка постановки: проверка шла мимо него"
    assert code == EXIT_BUSY
    assert f"прогон {opened} ещё идёт (queued); второй не запускается" in capsys.readouterr().err
    assert [one[0] for one in await _runs_after(before)] == [opened]


@pytest.mark.usefixtures("project")
async def test_console_opens_its_run_when_nothing_is_running() -> None:
    """M70: активных нет — консольный сбор открывает и закрывает прогон, как раньше."""
    before = await _last_run()

    code = await collect_commands._collect(only=[DOMAIN])

    opened = await _runs_after(before)
    assert code == 0
    assert [(status, email) for _, status, email in opened] == [(RunStatus.DONE, SYSTEM_USER_EMAIL)]
