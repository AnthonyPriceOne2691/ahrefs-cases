"""Прогон сбора: сто доменов, журнал, расход units.

Примеры приёмки: B6 (сто доменов без сети), B9 (короткая история помечена),
B10 (журнал units), B11 (пустая история — пропуск, прогон продолжается).

Сеть запрещается явно: `httpx` подменяется так, что любой исходящий запрос
падает. Без этого «без сети» проверялось бы доверием к fixture-провайдеру —
то есть не проверялось бы.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.runner import collect_all, collect_projects
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import read_csv
from ahrefs_cases.storage._enums import LedgerKind, ProjectStatus, RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run, RunItem
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
DOMAINS = 100


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """B6: любой HTTP-запрос в этих тестах — падение.

    Проверяется не «fixture не ходит в сеть» на словах, а то, что путь целиком —
    планирование, провайдер, запись — обходится без единого запроса наружу.
    """

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "прогон на фикстурах не имеет права ходить в сеть"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


def _list_file(path: Path, domains: list[str]) -> Path:
    lines = [COLUMNS]
    lines.extend(
        f"{domain},2025-01-01,2026-06-30,fintech,US,linkbuilding,10,Acme,i.petrov,yes,subdomains,"
        for domain in domains
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def _load(session: AsyncSession, tmp_path: Path, domains: list[str]) -> None:
    await accept(session, read_csv(_list_file(tmp_path / "list.csv", domains)))


async def test_hundred_domains_collected_without_network(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B6: сто синтетических доменов проходят целиком, серии оказываются в базе."""
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(DOMAINS)])

    report = await collect_all(db_session, AhrefsFixture())

    assert report.status == RunStatus.DONE.value
    assert report.projects_total == DOMAINS
    assert report.projects_ok == DOMAINS
    points = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert points == report.points_written > DOMAINS


async def test_units_ledger_has_a_row_per_request(db_session: AsyncSession, tmp_path: Path) -> None:
    """B10: строка журнала на каждый запрос, сумма — по модели стоимости."""
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(DOMAINS)])

    report = await collect_all(db_session, AhrefsFixture())

    rows = (await db_session.execute(select(UnitsLedger))).scalars().all()
    assert len(rows) == DOMAINS
    assert {row.endpoint for row in rows} == {METRICS_HISTORY.name}
    assert {row.kind for row in rows} == {LedgerKind.SPENT}
    assert all(row.units_estimated == row.units_actual for row in rows)
    assert report.units_spent == DOMAINS * METRICS_HISTORY.estimate_units() == 5000


async def test_empty_history_is_skipped_run_continues(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B11: домен без истории пропускается с причиной, остальные собираются."""
    await _load(db_session, tmp_path, ["empty.example.com", "d1.example.com", "young.example.com"])

    report = await collect_all(db_session, AhrefsFixture())

    assert report.status == RunStatus.DONE.value
    assert (report.projects_ok, report.projects_skipped) == (1, 2)
    items = (await db_session.execute(select(RunItem))).scalars().all()
    skipped = [item for item in items if item.outcome is RunItemOutcome.SKIPPED_NO_DATA]
    assert all(item.reason for item in skipped)
    assert all(item.units_actual == 0 for item in skipped)


async def test_short_history_is_marked_not_dropped(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B9: короткая история собирается и помечается — решать будет Ф3."""
    await _load(db_session, tmp_path, ["short.example.com"])

    await collect_all(db_session, AhrefsFixture())

    item = (await db_session.execute(select(RunItem))).scalars().one()
    assert item.outcome is RunItemOutcome.OK
    assert "short_history" in item.reason


async def test_repeat_run_updates_points_not_duplicates(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B21: повторный прогон переписывает точки, а не удваивает их.

    Это ещё не экономия Ф2б (запросы всё ещё делаются), но инвариант
    `(project, metric, date, source)`, на котором она будет стоять, обязан
    держаться уже сейчас — иначе кэш строился бы на дублирующихся строках.
    """
    await _load(db_session, tmp_path, ["d1.example.com"])
    first = await collect_all(db_session, AhrefsFixture())

    second = await collect_all(db_session, AhrefsFixture())

    total = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert first.points_written == second.points_written == total


async def test_project_status_follows_collection(db_session: AsyncSession, tmp_path: Path) -> None:
    """B21: статус проекта двигает прогон — собран → `collected`, пуст → `skipped`."""
    await _load(db_session, tmp_path, ["d1.example.com", "empty.example.com"])

    await collect_all(db_session, AhrefsFixture())

    projects = (await db_session.execute(select(Project))).scalars().all()
    by_domain = {project.domain: project.status for project in projects}
    assert by_domain["d1.example.com"] is ProjectStatus.COLLECTED
    assert by_domain["empty.example.com"] is ProjectStatus.SKIPPED


async def test_failed_provider_does_not_stop_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B21: падение по одному домену — `partial`, а не потеря всего прогона."""
    from ahrefs_cases.collect.ahrefs_transport import AhrefsUnavailableError
    from ahrefs_cases.collect.endpoints import EndpointSpec
    from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult

    class FlakyProvider(AhrefsFixture):
        async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
            if request.target == "d2.example.com":
                message = "Ahrefs не ответил за 3 попыт(ок)"
                raise AhrefsUnavailableError(message)
            return await super().fetch_history(spec, request)

    await _load(db_session, tmp_path, ["d1.example.com", "d2.example.com", "d3.example.com"])

    report = await collect_all(db_session, FlakyProvider())

    assert report.status == RunStatus.PARTIAL.value
    assert (report.projects_ok, report.projects_failed) == (2, 1)


async def test_run_snapshot_records_how_it_was_collected(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """B21: снимок параметров — через полгода «почему такие числа» упрётся в них."""
    await _load(db_session, tmp_path, ["d1.example.com"])

    await collect_projects(
        db_session,
        list((await db_session.execute(select(Project))).scalars().all()),
        AhrefsFixture(),
    )

    run = (await db_session.execute(select(Run))).scalars().one()
    assert run.params_snapshot["provider"] == "fixture"
    assert run.params_snapshot["history_grouping"] == "monthly"
    assert run.params_snapshot["fixture_seed"] == 42
