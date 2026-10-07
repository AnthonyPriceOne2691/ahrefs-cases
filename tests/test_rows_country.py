"""Купленные ряды помнят страну (Z53). Примеры приёмки: M79–M86.

Точка ряда различалась проектом, метрикой, месяцем и источником — страны среди них не
было. Месяцы кампании сайта по US переходили его кампании по DE как «уже купленные», а
после смены первой страны цифры оставались по прежней, и никто этого не видел. Решение
владельца 07.10.2026 — не докупать, а предупреждать.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.routers.projects import project_card
from ahrefs_cases.cases.model import CaseData, Change, Period
from ahrefs_cases.cases.narrative import compose
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.series import bought_countries
from ahrefs_cases.collect.cache import share_twin_points
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.quota import FixtureQuota
from ahrefs_cases.collect.runner import collect_projects
from ahrefs_cases.collect.scheme import PointWindows
from ahrefs_cases.export.brief_sheet import brief_sections
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import read_csv
from ahrefs_cases.intake.report import IntakeReport
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.geo import rows_note
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
SITE = "twin-country.example"
OTHER = "other-country.example"
NOTE = "цифры Ahrefs куплены по стране США (US) — до того, как первой страной проекта стала Германия (DE)"
NOW = date(2026, 9, 15)
QUOTA = FixtureQuota(left=200_000)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сбор на фикстурах не ходит в сеть: любой HTTP-запрос — падение."""

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "сбор на фикстурах не имеет права ходить в сеть"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


async def _campaigns(
    session: AsyncSession, tmp_path: Path, *rows: tuple[str, str, str]
) -> list[Project]:
    """Кампании одного сайта: (начало, конец, гео) — в порядке начала периода."""
    lines = [COLUMNS]
    lines.extend(
        f"{SITE},{start},{end},fintech,{geo},seo,10,Acme,i.petrov,yes,subdomains,"
        for start, end, geo in rows
    )
    path = tmp_path / "campaigns.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    await accept(session, read_csv(path))
    stmt = select(Project).where(Project.domain == SITE).order_by(Project.period_start)
    return list((await session.execute(stmt)).scalars().all())


async def test_twins_share_months_only_within_one_country(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """M81: месяцы кампании по US не переходят кампании по DE; другой кампании по US — переходят."""
    bought, other_us, by_de = await _campaigns(
        db_session,
        tmp_path,
        ("2025-01-01", "2025-12-31", "US"),
        ("2025-02-01", "2026-01-31", "US"),
        ("2025-03-01", "2026-02-28", "DE"),
    )
    await collect_projects(db_session, [bought], AhrefsFixture(), quota=QUOTA, now=NOW)

    to_de = await share_twin_points(
        db_session, [by_de], source=MetricSource.FIXTURE, windows=PointWindows()
    )
    to_us = await share_twin_points(
        db_session, [other_us], source=MetricSource.FIXTURE, windows=PointWindows()
    )

    assert to_de == 0, "кампания по DE получила месяцы, купленные по US"
    assert to_us > 0


async def _intake(session: AsyncSession, tmp_path: Path, *rows: tuple[str, str]) -> IntakeReport:
    """Список «домен, гео» с одним периодом на всех — как его загружает человек."""
    lines = [COLUMNS]
    lines.extend(
        f'{domain},2025-01-01,2025-12-31,fintech,"{geo}",seo,10,Acme,i.petrov,yes,subdomains,'
        for domain, geo in rows
    )
    path = tmp_path / "list.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return await accept(session, read_csv(path))


async def _project(session: AsyncSession, domain: str) -> Project:
    found = await session.execute(select(Project).where(Project.domain == domain))
    return found.scalars().one()


async def _buy(session: AsyncSession, *projects: Project, refresh: bool = False) -> None:
    await collect_projects(
        session, list(projects), AhrefsFixture(), quota=QUOTA, now=NOW, refresh=refresh
    )


async def _countries(session: AsyncSession, project: Project) -> tuple[str, ...]:
    return await bought_countries(session, project.id, MetricSource.FIXTURE)


async def test_points_remember_the_country_they_were_bought_for(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """M79: ряды проекта «DE, AT» куплены по DE; у «всего мира» страна пустая."""
    await _intake(db_session, tmp_path, (SITE, "DE, AT"), (OTHER, "Worldwide"))
    several, world = await _project(db_session, SITE), await _project(db_session, OTHER)

    await _buy(db_session, several, world)

    assert await _countries(db_session, several) == ("DE",)
    assert await _countries(db_session, world) == ("",)


async def test_intake_notes_a_new_first_country_of_bought_rows(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """M82: у проекта с купленными рядами сменилась первая страна — замечание, проект принят."""
    await _intake(db_session, tmp_path, (SITE, "US"))
    await _buy(db_session, await _project(db_session, SITE))

    report = await _intake(db_session, tmp_path, (SITE, "DE"))

    told = [(item.row_no, item.field, item.reason.value, item.detail) for item in report.notices]
    assert told == [(2, "geo", "geo_changed", "США (US) → Германия (DE)")]
    assert report.accepted == 1
    assert (await _project(db_session, SITE)).geo == "DE"


async def test_intake_stays_quiet_without_rows_or_without_a_new_first_country(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """M83: без рядов, при той же первой стране и при возврате к стране рядов — замечаний нет."""
    await _intake(db_session, tmp_path, (SITE, "US"), (OTHER, "US"))
    await _buy(db_session, await _project(db_session, OTHER))

    first = await _intake(db_session, tmp_path, (SITE, "DE"), (OTHER, "US, CA"))
    moved = await _intake(db_session, tmp_path, (OTHER, "DE"))
    back = await _intake(db_session, tmp_path, (OTHER, "US"))

    assert first.notices == ()
    assert [item.detail for item in moved.notices] == ["США (US) → Германия (DE)"]
    assert back.notices == ()


async def test_card_names_the_country_of_the_numbers(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """M84: оговорка в карточке — после смены страны, у смешанного ряда; у своей страны — нет."""
    await seed_thresholds(db_session)
    await _intake(db_session, tmp_path, (SITE, "US"), (OTHER, "DE"))
    changed, steady = await _project(db_session, SITE), await _project(db_session, OTHER)
    await _buy(db_session, changed, steady)
    await _intake(db_session, tmp_path, (SITE, "DE"), (OTHER, "DE"))

    after_change = await project_card(changed.id, db_session, source=MetricSource.FIXTURE)
    db_session.add(
        MetricPoint(
            project_id=changed.id,
            metric=Metric.ORG_TRAFFIC,
            point_date=date(2026, 8, 1),
            value=1.0,
            source=MetricSource.FIXTURE,
            country="DE",
            fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()
    mixed = await project_card(changed.id, db_session, source=MetricSource.FIXTURE)
    own = await project_card(steady.id, db_session, source=MetricSource.FIXTURE)

    assert after_change.geo_note == NOTE
    assert mixed.geo_note == "часть " + NOTE.replace("цифры Ahrefs куплены", "цифр Ahrefs куплена")
    assert own.geo_note is None


def test_note_names_the_world_and_several_countries() -> None:
    """M84: «весь мир» и несколько прежних стран называются словами."""
    assert rows_note("WW", ["US"]) == (
        "цифры Ahrefs куплены по стране США (US) — до того, как проект перевели на весь мир"
    )
    assert rows_note("DE", [""]) == (
        "цифры Ahrefs куплены по всему миру — до того, как первой страной проекта стала Германия (DE)"
    )
    assert rows_note("DE", ["US", "CA"]) == (
        "цифры Ahrefs куплены по странам Канада (CA), США (US) — "
        "до того, как первой страной проекта стала Германия (DE)"
    )
    assert rows_note("DE,AT", ["DE"]) is None


def _case(geo: str, note: str | None) -> CaseData:
    change = Change("org_traffic", Delta(before=1000.0, after=2600.0, absolute=1600.0, pct=160.0))
    return CaseData(
        title="tours.example",
        anonymized=False,
        geo=geo,
        niche="путешествия",
        service="seo",
        period=Period(start=date(2024, 10, 1), end=date(2025, 9, 1)),
        work_volume=120,
        group=Group.GOOD,
        ruleset_version="2026-10-A",
        changes=(change,),
        domain="tours.example",
        geo_note=note,
    )


def test_sheet_and_case_text_carry_the_note() -> None:
    """M85: строка «ГЕО» и текст кейса называют страну цифр, а не обещают «по первой из них»."""
    case = _case("DE,AT", NOTE)
    rows = {row.label: row.value for section in brief_sections(case) for row in section.rows}
    text = compose(case)

    assert rows["ГЕО"] == f"Германия (DE), Австрия (AT); {NOTE}"
    assert NOTE in text
    assert "по первой из них" not in text
    assert "по первой из них" in compose(replace(case, geo_note=None))


async def test_refresh_rewrites_the_country(db_session: AsyncSession, tmp_path: Path) -> None:
    """M86: перепокупка по новой стране переписывает страну точек — оговорки больше нет."""
    await _intake(db_session, tmp_path, (SITE, "US"))
    project = await _project(db_session, SITE)
    await _buy(db_session, project)
    await _intake(db_session, tmp_path, (SITE, "DE"))

    await _buy(db_session, project, refresh=True)

    assert await _countries(db_session, project) == ("DE",)
    assert rows_note(project.geo, await _countries(db_session, project)) is None
