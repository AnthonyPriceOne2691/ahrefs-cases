"""Двухступенчатая воронка: за «плохих» дорогие метрики не платятся.

Пример приёмки: C9. Проверяется числом запросов и содержимым базы: сказать
«шаг 2 только кандидатам» можно и продолжая спрашивать всех, а разница видна
только в счёте.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.endpoints import DOMAIN_RATING_HISTORY, EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.funnel import preliminary_candidates
from ahrefs_cases.collect.plan import stage2_specs
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.runner import collect_all, collect_stage2
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)

GROWING = ["d0.example.com", "d7.example.com", "d14.example.com"]
"""Домены со сценарием `steady_growth` в data/fixtures/scenarios.yml."""

FALLING = ["d2.example.com", "d9.example.com", "d16.example.com"]
"""Домены со сценарием `decline` — по ним кейса не будет."""


class CountingFixture(AhrefsFixture):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str]] = []

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append((spec.name, request.target))
        return await super().fetch_history(spec, request)


async def _load(session: AsyncSession, domains: list[str]) -> None:
    rows = "\n".join(
        f"{domain},2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for domain in domains
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))


async def _ids(session: AsyncSession) -> dict[str, int]:
    projects = (await session.execute(select(Project))).scalars().all()
    return {project.domain: project.id for project in projects}


async def test_prefilter_keeps_growth_and_drops_decline(db_session: AsyncSession) -> None:
    """C9: кандидатами становятся выросшие, а не все подряд."""
    await _load(db_session, GROWING + FALLING)
    await collect_all(db_session, AhrefsFixture(), now=NOW)
    ids = await _ids(db_session)

    candidates = await preliminary_candidates(
        db_session, list(ids.values()), source=MetricSource.FIXTURE
    )

    assert sorted(candidates) == sorted(ids[domain] for domain in GROWING)


async def test_stage2_asks_only_candidates(db_session: AsyncSession) -> None:
    """C9: шаг 2 делает запросы ровно по кандидатам.

    «Плохие» не получают дорогих метрик ни в журнале, ни в базе — это и есть
    экономия воронки, и меряется она числом запросов, а не намерением.
    """
    await _load(db_session, GROWING + FALLING)
    await collect_all(db_session, AhrefsFixture(), now=NOW)
    ids = await _ids(db_session)
    candidates = await preliminary_candidates(
        db_session, list(ids.values()), source=MetricSource.FIXTURE
    )
    provider = CountingFixture()

    report = await collect_stage2(db_session, candidates, provider, now=NOW)

    asked = {domain for _endpoint, domain in provider.calls}
    assert asked == set(GROWING)
    assert report.requests_made == len(GROWING) * len(stage2_specs())


async def test_declining_projects_have_no_expensive_metrics(db_session: AsyncSession) -> None:
    """C9: у «плохих» в базе нет метрик шага 2 — за них не платили."""
    await _load(db_session, GROWING + FALLING)
    await collect_all(db_session, AhrefsFixture(), now=NOW)
    ids = await _ids(db_session)
    candidates = await preliminary_candidates(
        db_session, list(ids.values()), source=MetricSource.FIXTURE
    )

    await collect_stage2(db_session, candidates, AhrefsFixture(), now=NOW)

    for domain in FALLING:
        stmt = select(MetricPoint).where(
            MetricPoint.project_id == ids[domain],
            MetricPoint.metric.in_([Metric.REFDOMAINS, Metric.KW_TOP3]),
        )
        assert (await db_session.execute(stmt)).scalars().all() == []


async def test_project_without_data_is_not_a_candidate(db_session: AsyncSession) -> None:
    """C9: платить за дорогие метрики там, где нет дешёвых, — покупать пустой кейс."""
    await _load(db_session, ["empty.example.com"])
    await collect_all(db_session, AhrefsFixture(), now=NOW)
    ids = await _ids(db_session)

    candidates = await preliminary_candidates(
        db_session, list(ids.values()), source=MetricSource.FIXTURE
    )

    assert candidates == []


def test_dr_history_is_behind_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """C9: DR стоит как полноценный запрос, а группу не определяет.

    Флаг выключен по умолчанию: включать надо осознанно, потому что это чистая
    надбавка к цене прогона.
    """
    monkeypatch.setattr(config.ahrefs, "collect_dr_history", False)
    assert DOMAIN_RATING_HISTORY not in stage2_specs()

    monkeypatch.setattr(config.ahrefs, "collect_dr_history", True)
    assert DOMAIN_RATING_HISTORY in stage2_specs()
