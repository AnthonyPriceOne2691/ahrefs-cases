"""Устойчивость прогона: ошибки, предохранитель, чекпойнты, реапер.

Примеры приёмки: C11 (реапер зависших), C12 (чужое исключение не валит прогон),
C13 (падение вне задач закрывает прогон статусом), C14 (предохранитель),
C16 (прерванный прогон сохраняет собранное), C17 (пустой домен не покупается
дважды).

Все эти случаи — про поведение при беде, и проверять их надо именно так:
подсовывая беду, а не читая код.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsUnavailableError
from ahrefs_cases.collect.breaker import ConsecutiveFailureBreaker
from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.run_journal import open_run, system_user
from ahrefs_cases.collect.run_reaper import reap_stale_runs
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.run import Run, RunItem

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)


async def _load(session: AsyncSession, domains: list[str]) -> None:
    rows = "\n".join(
        f"{domain},2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for domain in domains
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))


class CountingFixture(AhrefsFixture):
    """Фикстура, считающая обращения: «запросов не было» доказывается числом."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append(request.target)
        return await super().fetch_history(spec, request)


class CrashingFixture(CountingFixture):
    """Провайдер, который бросает **чужое** исключение — не из нашей иерархии."""

    def __init__(self, on_domain: str) -> None:
        super().__init__()
        self._on_domain = on_domain

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        if request.target == self._on_domain:
            message = "ключа 'metrics' нет в ответе"
            raise KeyError(message)
        return await super().fetch_history(spec, request)


class AlwaysFailingFixture(CountingFixture):
    """Ahrefs лёг: каждый запрос — известная ошибка недоступности."""

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append(request.target)
        message = "Ahrefs не ответил за 3 попыт(ок)"
        raise AhrefsUnavailableError(message)


async def test_foreign_exception_does_not_kill_the_run(db_session: AsyncSession) -> None:
    """C12: `KeyError` из разбора ответа роняет один проект, а не прогон.

    Именно чужое исключение, а не наш `AhrefsUnavailableError`: до этой правки
    ловились только свои типы, и любая неожиданность обрывала `gather` вместе
    с сотней доменов.
    """
    await _load(db_session, ["d1.example.com", "d2.example.com", "d3.example.com"])

    report = await collect_all(db_session, CrashingFixture("d2.example.com"), now=NOW)

    assert report.status == RunStatus.PARTIAL.value
    assert (report.projects_ok, report.projects_failed) == (2, 1)
    failed = (
        (await db_session.execute(select(RunItem).where(RunItem.outcome == RunItemOutcome.FAILED)))
        .scalars()
        .one()
    )
    assert "KeyError" in failed.reason


async def test_failure_outside_tasks_closes_the_run(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C13: падение записи закрывает прогон статусом и пробрасывает ошибку.

    Молча проглотить — соврать вызывающему успехом; не закрыть прогон —
    оставить строку в `running` навсегда вместе с её резервом units.
    """
    await _load(db_session, ["d1.example.com"])

    async def boom(*_args: object, **_kwargs: object) -> int:
        message = "диск кончился"
        raise RuntimeError(message)

    monkeypatch.setattr("ahrefs_cases.collect.runner.store_history", boom)

    with pytest.raises(RuntimeError, match="диск кончился"):
        await collect_all(db_session, AhrefsFixture(), now=NOW)

    run = (await db_session.execute(select(Run))).scalars().one()
    assert run.status is RunStatus.FAILED
    assert "RuntimeError" in run.error


async def test_breaker_stops_the_run_and_saves_the_rest(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C14: после серии неудач оставшиеся домены не запрашиваются.

    При лежащем Ahrefs каждый следующий запрос — оплаченный таймаут. Проверяем
    числом обращений к провайдеру, а не статусом: статус можно поставить и
    продолжая жечь квоту.
    """
    monkeypatch.setattr(config.ahrefs, "breaker_max_failures", 3)
    monkeypatch.setattr(config.ahrefs, "max_parallel", 1)
    domains = [f"d{index}.example.com" for index in range(10)]
    await _load(db_session, domains)
    provider = AlwaysFailingFixture()

    report = await collect_all(db_session, provider, now=NOW)

    assert len(provider.calls) == 3
    assert report.projects_aborted == len(domains) - 3
    aborted = (
        (
            await db_session.execute(
                select(RunItem).where(RunItem.outcome == RunItemOutcome.SKIPPED_ABORTED)
            )
        )
        .scalars()
        .all()
    )
    assert all("предохранителем" in item.reason for item in aborted)


def test_breaker_counts_consecutive_not_total() -> None:
    """Обратная сторона C14: одиночные ошибки прогон не останавливают.

    Домен со странным ответом — норма. Считай предохранитель ошибки суммарно,
    он срабатывал бы на любом длинном списке, где беды нет вовсе.
    """
    breaker = ConsecutiveFailureBreaker(limit=3)

    for ok in (False, False, True, False, False, True, False):
        breaker.record(ok=ok)

    assert not breaker.tripped


async def test_interrupted_run_keeps_what_it_collected(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C16: прогон, упавший на середине, не становится тратой.

    Два домена уже записаны и оплачены — они обязаны остаться. Следующий
    запуск догружает только недостающее: возобновления как отдельного
    механизма нет, его роль играет кэш.
    """
    monkeypatch.setattr(config.ahrefs, "checkpoint_every", 1)
    monkeypatch.setattr(config.ahrefs, "max_parallel", 1)
    domains = [f"d{index}.example.com" for index in range(5)]
    await _load(db_session, domains)

    real_store = __import__("ahrefs_cases.collect.series", fromlist=["store_history"]).store_history
    calls = {"n": 0}

    async def store_twice_then_die(*args: object, **kwargs: object) -> int:
        calls["n"] += 1
        if calls["n"] > 2:
            message = "база отвалилась"
            raise RuntimeError(message)
        return await real_store(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("ahrefs_cases.collect.runner.store_history", store_twice_then_die)

    with pytest.raises(RuntimeError):
        await collect_all(db_session, AhrefsFixture(), now=NOW)

    saved = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert saved > 0, "данные двух собранных доменов пропали — прогон стал чистой тратой"

    monkeypatch.setattr("ahrefs_cases.collect.runner.store_history", real_store)
    provider = CountingFixture()
    await collect_all(db_session, provider, now=NOW)

    assert len(provider.calls) == len(domains) - 2, "докупили не только недостающее"


async def test_empty_domain_is_not_bought_twice(db_session: AsyncSession) -> None:
    """C17: домен без истории не перезапрашивается следующим прогоном.

    Он не оставляет точек, поэтому обычный кэш о нём не знает: без памяти о
    пустом ответе десять молодых доменов в списке покупают одну и ту же
    пустоту каждый месяц. Дыра найдена сверкой с CRM агентства.
    """
    await _load(db_session, ["empty.example.com", "d1.example.com"])
    await collect_all(db_session, AhrefsFixture(), now=NOW)

    provider = CountingFixture()
    second = await collect_all(db_session, provider, now=NOW)

    assert provider.calls == []
    assert second.requests_saved == 2


async def test_empty_memory_expires(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Обратная сторона C17: молодой домен когда-нибудь перестаёт быть молодым."""
    await _load(db_session, ["empty.example.com"])
    await collect_all(db_session, AhrefsFixture(), now=NOW)
    monkeypatch.setattr(config.ahrefs, "empty_retry_days", 0)

    provider = CountingFixture()
    await collect_all(db_session, provider, now=NOW)

    assert provider.calls == ["empty.example.com"]


async def test_reaper_closes_stale_run(db_session: AsyncSession) -> None:
    """C11: прогон, простоявший в `running` дольше порога, закрывается с причиной."""
    user = await system_user(db_session)
    run = await open_run(db_session, started_by=user.id, projects_total=1)
    run.started_at = datetime.now(UTC) - timedelta(seconds=config.ahrefs.run_stale_sec + 60)
    await db_session.flush()

    reaped = await reap_stale_runs(db_session)

    await db_session.refresh(run)
    assert reaped == [run.id]
    assert run.status is RunStatus.FAILED
    assert "реапером" in run.error


async def test_reaper_does_not_touch_fresh_run(db_session: AsyncSession) -> None:
    """Обратная сторона C11: идущий прогон не должен быть добит реапером."""
    user = await system_user(db_session)
    run = await open_run(db_session, started_by=user.id, projects_total=1)

    reaped = await reap_stale_runs(db_session)

    assert reaped == []
    assert run.status is RunStatus.RUNNING


async def test_reaper_does_not_overwrite_finished_run(db_session: AsyncSession) -> None:
    """C11: прогон, успевший финишировать, свой статус сохраняет.

    Guarded UPDATE вместо блокировки: гонка реапера с честным завершением —
    штатная ситуация, а не редкость, потому что реапер бежит именно тогда,
    когда прогоны идут долго.
    """
    user = await system_user(db_session)
    run = await open_run(db_session, started_by=user.id, projects_total=1)
    run.started_at = datetime.now(UTC) - timedelta(seconds=config.ahrefs.run_stale_sec + 60)
    run.status = RunStatus.DONE
    await db_session.flush()

    reaped = await reap_stale_runs(db_session)

    assert reaped == []
    assert run.status is RunStatus.DONE
