"""Прогон сбора: сто доменов, журнал, расход units.

Примеры приёмки: B6 (сто доменов без сети), B9 (короткая история помечена),
B10 (журнал units), B11 (пустая история — пропуск, прогон продолжается).

Сеть запрещается явно: `httpx` подменяется так, что любой исходящий запрос
падает. Без этого «без сети» проверялось бы доверием к fixture-провайдеру —
то есть не проверялось бы.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.quota import FixtureQuota
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
NOW = date(2026, 9, 15)
"""Граница закрытого месяца передаётся явно: период работ в списке кончается
2026-06-30, значит всё окно закрыто и кэш обязан срабатывать целиком."""

BIG_QUOTA = FixtureQuota(left=200_000)
"""Квота, заведомо покрывающая прогон на сотню доменов.

Указывается явно, потому что бюджет заказчика (10 000) такой прогон **не
покрывает**: по замеренной цене он стоит 44 100 units. Это отдельная находка
и отдельный тест (`test_hundred_domains_do_not_fit_customer_budget`); здесь же
проверяется механика сбора, и подменять её проверкой бюджета нельзя."""


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

    report = await collect_all(db_session, AhrefsFixture(), quota=BIG_QUOTA)

    assert report.status == RunStatus.DONE.value
    assert report.projects_total == DOMAINS
    assert report.projects_ok == DOMAINS
    points = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert points == report.points_written > DOMAINS


async def test_units_ledger_has_a_row_per_request(db_session: AsyncSession, tmp_path: Path) -> None:
    """B10: строка журнала на каждый запрос, сумма — по модели стоимости."""
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(DOMAINS)])

    report = await collect_all(db_session, AhrefsFixture(), quota=BIG_QUOTA)

    rows = (
        (await db_session.execute(select(UnitsLedger).where(UnitsLedger.kind == LedgerKind.SPENT)))
        .scalars()
        .all()
    )
    assert len(rows) == DOMAINS
    assert {row.endpoint for row in rows} == {METRICS_HISTORY.name}
    assert {row.kind for row in rows} == {LedgerKind.SPENT}
    assert all(row.units_estimated == row.units_actual for row in rows)
    # Цена построчная, поэтому она РАЗНАЯ у разных доменов: у сценария с
    # короткой историей строк четыре, с дырой — пятнадцать. Прибивать сумму к
    # числу значит проверять раскладку сценариев, а не модель стоимости.
    assert report.units_spent == sum(row.units_actual or 0 for row in rows)
    assert report.units_spent > DOMAINS * METRICS_HISTORY.estimate_units(rows=1), (
        "цена не выросла с числом строк — модель стоимости снова «за запрос»"
    )


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


async def test_second_run_asks_nothing(db_session: AsyncSession, tmp_path: Path) -> None:
    """C1: второй прогон по тому же списку не делает ни одного запроса.

    Считаются оба прогона, а не только второй: «ноль запросов» у одного лишь
    второго прогона одинаково хорошо доказывает и работающий кэш, и сломанный
    сбор. Первый обязан сделать свой запрос, второй — не сделать ни одного.
    """
    await _load(db_session, tmp_path, ["d1.example.com"])

    first = await collect_all(db_session, AhrefsFixture(), now=NOW)
    second = await collect_all(db_session, AhrefsFixture(), now=NOW)

    assert (first.requests_made, first.requests_saved) == (1, 0)
    assert (second.requests_made, second.requests_saved) == (0, 1)
    assert second.units_spent == 0
    total = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert total == first.points_written


async def test_second_run_ledger_is_all_cached(db_session: AsyncSession, tmp_path: Path) -> None:
    """C10: экономия предъявлена журналом, а не отсутствием строк.

    Прогон без единой строки в `UnitsLedger` неотличим от прогона, который не
    состоялся. Строки `kind=cached` и есть ответ на вопрос «во что обошёлся
    второй запуск».
    """
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(5)])
    await collect_all(db_session, AhrefsFixture(), now=NOW)

    second = await collect_all(db_session, AhrefsFixture(), now=NOW)

    rows = (
        (
            await db_session.execute(
                select(UnitsLedger).where(
                    UnitsLedger.run_id == second.run_id,
                    # Строка резерва в счёт не идёт: она про намерение, а не
                    # про запрос. Считаем то, что объясняет счёт от Ahrefs.
                    UnitsLedger.kind != LedgerKind.RESERVE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 5
    assert {row.kind for row in rows} == {LedgerKind.CACHED}
    assert second.requests_saved == 5


async def test_refresh_rewrites_points_without_duplicating(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """C18: принудительное обновление снова платит — и не удваивает точки.

    Инвариант `(project, metric, date, source)` проверяется именно здесь: при
    обычном втором прогоне запись не происходит вовсе, и `ON CONFLICT` остался
    бы непроверенным ровно с той поставки, где на нём стоит вся экономия.
    """
    await _load(db_session, tmp_path, ["d1.example.com"])
    first = await collect_all(db_session, AhrefsFixture(), now=NOW)

    forced = await collect_all(db_session, AhrefsFixture(), now=NOW, refresh=True)

    assert forced.requests_made == 1
    total = (await db_session.execute(select(func.count()).select_from(MetricPoint))).scalar_one()
    assert total == first.points_written == forced.points_written


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


async def test_hundred_domains_do_not_fit_customer_budget(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Прогон по ТЗ не влезает в бюджет ТЗ — и это надо знать до Ф7.

    Заказчик называет 10 000 units на первичный прогон по сотне доменов.

    Число менялось дважды, и обе правки видны здесь, как и обещал прежний
    докстринг. Было 44 100 — 21 строка по 21 unit. Стало **19 800**: ушло
    второе поле (`org_cost`, читателя не имел) и три месяца запаса до старта
    работ, которых не просил никто. Preflight по-прежнему отказывает, и
    по-прежнему правильно: прогон, начатый вслепую, съел бы квоту на половине
    списка.

    Тест закрепляет факт, а не желаемое. Схема «две точки» это число тоже
    меняет — см. соседний тест, где она включена флагом.
    """
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(DOMAINS)])

    report = await collect_all(
        db_session, AhrefsFixture(), now=NOW, quota=FixtureQuota(left=10_000)
    )

    assert report.status == RunStatus.FAILED.value
    assert report.requests_made == 0
    assert "не хватает units" in report.error
    assert report.units_estimated == 19_800


async def test_scheme_auto_halves_the_estimate_and_says_so(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E11: схема `auto` вдвое дешевле, и отчёт показывает разбивку по способу.

    Период списка — 18 месяцев, то есть точки дешевле истории (100 против 198
    на домен). Сотня доменов: 19 800 историей против 10 000 точками.

    Отчёт обязан назвать оба числа и «стоимость запуска на 100 URL» — это
    метрика приёмки, которую заказчик назвал сам, и выводить её из журнала
    руками он не должен. Метрика — цена **прогона на сотню URL** (10 000), а не
    на домен (100): сравнивать прогоны между собой можно только так.
    """
    monkeypatch.setattr(config.ahrefs, "collect_scheme", "auto")
    await _load(db_session, tmp_path, [f"d{index}.example.com" for index in range(DOMAINS)])

    report = await collect_all(
        db_session, AhrefsFixture(), now=NOW, quota=FixtureQuota(left=200_000)
    )

    assert report.units_estimated == 10_000
    assert report.cost_per_100 == 10_000, "цена прогона на сотню URL, то есть 100 на домен"
    assert report.requests_made == 2 * DOMAINS, "две точки — два запроса на домен"
    assert report.projects_total == DOMAINS, "проектов сто, а не двести (L13)"
    breakdown = "\n".join(report.scheme_lines)
    assert "two_points: 100 проект(ов), 10000 units" in breakdown
    assert "19800" in breakdown, "отчёт называет цену альтернативы, иначе смета необъяснима"
