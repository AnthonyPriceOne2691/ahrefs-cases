"""Текст кейса по числам, подсветка и запись кейса в базу.

Примеры приёмки поставки `case-narrative`: E1 (текст называет результат), E2
(чужое число роняет сборку), E3 (формат один), E4 (рост от нуля), E5 (пустой
объём работ), E6 (подсветка), E7 (нет утверждений о работах), E8 (запись),
E9 (версия), E10 (стоп-лист смотрит на текст).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases import highlights as highlights_module
from ahrefs_cases.cases import narrative as narrative_module
from ahrefs_cases.cases.format import number
from ahrefs_cases.cases.model import CaseData, Change, Period
from ahrefs_cases.cases.stoplist import check
from ahrefs_cases.cases.store import next_version, store_artifact, store_case
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.classify.points import KW_TOP10
from ahrefs_cases.storage._enums import CaseStatus, Group, ProjectStatus
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict


def _change(subject: str, before: float, after: float) -> Change:
    pct = ((after - before) / before) * 100 if before > 0 else None
    return Change(
        subject=subject, delta=Delta(before=before, after=after, absolute=after - before, pct=pct)
    )


def _case(changes: tuple[Change, ...] | None = None, **overrides: object) -> CaseData:
    changes = changes or (
        _change("org_traffic", 47326.0, 113312.0),
        _change(KW_TOP10, 710.0, 1700.0),
        _change("refdomains", 854.0, 800.0),
    )
    fields: dict[str, object] = {
        "title": "example.com",
        "anonymized": False,
        "geo": "US",
        "niche": "fintech",
        "service": "linkbuilding",
        "period": Period(start=date(2025, 1, 1), end=date(2026, 6, 1)),
        "work_volume": 120,
        "group": Group.GOOD,
        "ruleset_version": "2026-09-A",
        "changes": changes,
        "highlights": highlights_module.pick(changes),
    }
    fields.update(overrides)
    case = CaseData(**fields)  # type: ignore[arg-type]
    return CaseData(**{**fields, "narrative": narrative_module.compose(case)})  # type: ignore[arg-type]


def test_text_names_the_main_result() -> None:
    """E1 и E3: главная метрика, процент и обе границы — в том же формате, что в таблице."""
    text = _case().narrative

    assert "органический трафик" in text.lower()
    assert "139 %" in text
    assert f"с {number(47326.0)} до {number(113312.0)}" in text


def test_number_absent_from_the_case_breaks_composition() -> None:
    """E2: подмена цифры не должна дожить до артефакта."""
    case = _case()

    with pytest.raises(narrative_module.NumbersMismatchError):
        narrative_module.verify_numbers(case.narrative + " Рост составил 999 визитов.", case)


def test_growth_from_zero_has_no_percent() -> None:
    """E4: «+∞ %» в текст не попадает."""
    changes = (
        _change("org_traffic", 1000.0, 1200.0),
        _change("refdomains", 0.0, 12.0),
    )
    text = _case(changes).narrative

    assert "с нуля до 12" in text
    assert "%" in text  # у трафика процент есть — исчез только у роста от нуля


def test_empty_work_volume_has_no_sentence() -> None:
    """E5: объём работ — единственное, что мы знаем о самих работах."""
    assert "Объём работ" in _case().narrative
    assert "Объём работ" not in _case(work_volume=None).narrative


def test_highlights_put_traffic_first_and_skip_what_fell() -> None:
    """E6: трафик — главная метрика ТЗ; упавшее не подсвечивается."""
    case = _case()
    picked = [item.subject for item in case.highlights]

    assert picked[0] == "org_traffic"
    assert "refdomains" not in picked  # ссылки в примере упали


def test_text_claims_nothing_about_the_work_itself() -> None:
    """E7: ИИ или шаблон, всё равно — мы не знаем, какие работы велись."""
    text = _case().narrative.lower()

    assert "благодаря" not in text
    for claim in ("мы ", "оптимизировали", "построили", "настроили", "написали"):
        assert claim not in text


def test_stoplist_reads_the_text_too() -> None:
    """E10: текст собран из полей того же входного файла."""
    clean = _case()
    assert check(clean) == ()

    dirty = replace(clean, narrative=clean.narrative + " Продвижение в Москве.")
    assert [hit.where for hit in check(dirty)] == ["текст"]


async def _project_with_verdict(session: AsyncSession) -> tuple[Project, int]:
    """Проект с вердиктом: кейс без вердикта в базе не живёт по построению."""
    project = Project(
        domain="stored.example",
        period_start=date(2025, 1, 1),
        period_end=date(2026, 6, 1),
        niche="fintech",
        geo="US",
        service_type="seo",
        client="Acme",
        owner="i.petrov",
        publishable=True,
        work_volume=120,
        notes="",
    )
    ruleset = Ruleset(version="2026-09-A", payload={}, is_active=True)
    session.add_all((project, ruleset))
    await session.flush()
    verdict = Verdict(
        project_id=project.id,
        ruleset_id=ruleset.id,
        group=Group.GOOD,
        score=0.0,
        reasons={},
        point_a={},
        point_b={},
    )
    session.add(verdict)
    await session.flush()
    return project, verdict.id


async def test_case_and_artifact_are_written(db_session: AsyncSession, tmp_path: Path) -> None:
    """E8: в базе появляются кейс и его файл с контрольной суммой."""
    project, verdict_id = await _project_with_verdict(db_session)
    artifact_path = tmp_path / "stored.example.pdf"
    artifact_path.write_bytes(b"%PDF-1.7 fake")

    row = await store_case(db_session, project_id=project.id, verdict_id=verdict_id, case=_case())
    artifact = await store_artifact(db_session, case_id=row.id, path=artifact_path)

    stored = (await db_session.execute(select(Case))).scalars().one()
    assert (stored.version, stored.status) == (1, CaseStatus.BUILT)
    assert stored.narrative.startswith("Проект в нише")
    assert stored.highlights["picked"][0]["subject"] == "org_traffic"
    assert (await db_session.execute(select(CaseArtifact))).scalars().one().checksum == (
        artifact.checksum
    )
    assert len(artifact.checksum) == 64
    assert (await db_session.get(Project, project.id)).status is ProjectStatus.CASE_READY


async def test_second_build_adds_a_version(db_session: AsyncSession) -> None:
    """E9: ТЗ требует перегенерации через полгода — сравнивать надо с чем-то."""
    project, verdict_id = await _project_with_verdict(db_session)

    first = await store_case(db_session, project_id=project.id, verdict_id=verdict_id, case=_case())
    second = await store_case(
        db_session, project_id=project.id, verdict_id=verdict_id, case=_case()
    )

    assert (first.version, second.version) == (1, 2)
    assert await next_version(db_session, project.id) == 3
