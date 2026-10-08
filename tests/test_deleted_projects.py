"""Удалённый и заново загруженный проект (Z40): пустота не покупается заново, прочерк не врёт.

Примеры приёмки поставки `deleted-projects-remembered`: M105, M106 — память о пустом домене; M107 — что по
домену покупали. M108 и M109 — в `tests/test_api_projects_delete.py`, рядом с удалением.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.purchases import bought_metrics
from ahrefs_cases.collect.run_journal import system_user
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.export.removal import delete_rows
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import LedgerKind, Metric, RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run, RunItem
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)
EMPTY = "empty.example.com"
"""Домен, которому фикстура отвечает пустой историей (`data/fixtures/scenarios.yml`)."""


class CountingFixture(AhrefsFixture):
    """Фикстура, считающая обращения: «не спрашивали» доказывается числом."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append(request.target)
        return await super().fetch_history(spec, request)


async def _load(session: AsyncSession, domain: str, start: str = "2025-01-01") -> Project:
    """Загрузить кампанию сайта так, как её загружает человек, — строкой списка."""
    row = f"{domain},{start},2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    stmt = select(Project).where(
        Project.domain == domain, Project.period_start == date.fromisoformat(start)
    )
    return (await session.execute(stmt)).scalar_one()


async def _confirm_empty(session: AsyncSession) -> None:
    """Спросить и переспросить: памяти о пустом домене нужно два пустых ответа подряд."""
    for _ in range(2):
        await collect_all(session, AhrefsFixture(), now=NOW)


async def test_empty_domain_memory_survives_deletion(db_session: AsyncSession) -> None:
    """M105: дважды пустой домен после удаления и новой загрузки не покупается снова.

    Прежде память держалась за номер проекта, а удаление его обнуляло: вживую это от 50 units
    за запрос и два подтверждения заново на каждый домен (M105, Z40).
    """
    gone = await _load(db_session, EMPTY)
    await _confirm_empty(db_session)
    await delete_rows(db_session, gone)
    await _load(db_session, EMPTY)

    again = CountingFixture()
    await collect_all(db_session, again, now=NOW)

    assert again.calls == []


async def test_live_campaigns_keep_their_own_memory(db_session: AsyncSession) -> None:
    """M106: у живых кампаний сайта память своя — вторую, не проверенную, сбор спрашивает."""
    await _load(db_session, EMPTY)
    await _confirm_empty(db_session)
    await _load(db_session, EMPTY, start="2024-01-01")

    again = CountingFixture()
    await collect_all(db_session, again, now=NOW)

    assert again.calls == [EMPTY]


async def _purchase(session: AsyncSession, project: Project, endpoint: str) -> None:
    """Прогон, где проекту купили `endpoint`: строка журнала и строка расхода, как их пишет сбор."""
    author = await system_user(session)
    run = Run(started_by=author.id, status=RunStatus.DONE, projects_total=1)
    session.add(run)
    await session.flush()
    session.add(
        RunItem(
            run_id=run.id,
            project_id=project.id,
            raw_domain=project.domain,
            outcome=RunItemOutcome.OK,
        )
    )
    session.add(
        UnitsLedger(
            run_id=run.id,
            kind=LedgerKind.SPENT,
            endpoint=endpoint,
            target=project.domain,
            units_actual=72,
        )
    )
    await session.flush()


async def test_purchases_of_a_deleted_project_are_not_the_new_ones(
    db_session: AsyncSession,
) -> None:
    """M107: покупка удалённого проекта не подписывает прочерк нового «нет у Ahrefs».

    Журнал расхода знает домен — значит не «неизвестно», а пусто: для нового проекта шаг 2 не
    делался, и прочерк — «не собирали». У живого проекта, чей шаг 2 прошёл без данных, — по-прежнему
    «нет у Ahrefs».
    """
    gone = await _load(db_session, "rebought.example.com")
    await _purchase(db_session, gone, "refdomains-history")
    await delete_rows(db_session, gone)
    await _load(db_session, "rebought.example.com")
    alive = await _load(db_session, "alive.example.com")
    await _purchase(db_session, alive, "refdomains-history")

    assert await bought_metrics(db_session, "rebought.example.com") == frozenset()
    assert Metric.REFDOMAINS in (await bought_metrics(db_session, "alive.example.com") or ())
