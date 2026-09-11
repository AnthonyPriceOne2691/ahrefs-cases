"""Структура кейса: числа, готовые к рендеру.

Примеры приёмки поставки `case-structure`: E1 (четыре исхода), E2 (числа из
записанного вердикта), E3 (анонимность), E4 (пустой объём работ), E5 (метрика
только в точке Б), E6 («число ключей» при всех пяти корзинах), E7 (вердикт
старше данных), E8 (точка чужой формы), E9 (детерминированность), E10 (версия
порогов из вердикта).

Кейс собирается **из вердикта**, поэтому большинство примеров чистые: точки
строятся в том же JSONB-виде, в каком их пишет `classify/verdicts.store`, а
серия — словарём. База нужна только там, где проверяется отбор проектов.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases.builder import (
    VerdictFormatError,
    VerdictView,
    build_case,
    build_cases,
    stale_subjects,
)
from ahrefs_cases.cases.model import KW_TOTAL, CaseOutcome
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2025, 12, 1)
VERSION = "2026-09-A"


def _project(**overrides: Any) -> Project:
    """Проект из входного файла. В базу не пишется: сборка кейса чистая."""
    fields: dict[str, Any] = {
        "id": 1,
        "domain": "example.com",
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "niche": "fintech",
        "geo": "US",
        "service_type": "seo",
        "client": "Acme",
        "owner": "i.petrov",
        "publishable": True,
        "work_volume": 120,
        "notes": "",
    }
    fields.update(overrides)
    return Project(**fields)


def _point(at: date, values: dict[str, float], derived: dict[str, float] | None = None) -> dict:
    """Точка в том же виде, в каком её записал `verdicts.store` (JSONB)."""
    return {
        "at": at.isoformat(),
        "months_used": 3,
        "values": values,
        "derived": derived or {},
    }


def _verdict(point_a: dict, point_b: dict, group: Group = Group.GOOD) -> Verdict:
    return Verdict(
        project_id=1,
        ruleset_id=1,
        group=group,
        score=0.0,
        reasons={},
        point_a=point_a,
        point_b=point_b,
    )


def _verdict_view(
    point_a: dict[str, float],
    point_b: dict[str, float],
    *,
    derived_a: dict[str, float] | None = None,
    derived_b: dict[str, float] | None = None,
) -> VerdictView:
    verdict = _verdict(
        _point(PERIOD_START, point_a, derived_a), _point(PERIOD_END, point_b, derived_b)
    )
    return VerdictView.of(verdict, Ruleset(id=1, version=VERSION, payload={}))


def test_numbers_come_from_the_recorded_verdict() -> None:
    """E2: кейс показывает числа вердикта, а не считает границы по серии.

    Гарантия структурная: `build_case` серии не видит вовсе. Считай он границы
    сам — разошёлся бы с таблицей классификации, и первым это заметил бы
    клиент, которому показали и то и другое.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2400.0})

    case = build_case(_project(), verdict, {})

    traffic = case.change(Metric.ORG_TRAFFIC.value)
    assert traffic is not None
    assert (traffic.before, traffic.after) == (1000.0, 2400.0)
    assert traffic.pct == pytest.approx(140.0)


def test_anonymous_case_never_names_the_domain() -> None:
    """E3: `publishable=false` — домена нет нигде в структуре."""
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})

    case = build_case(_project(publishable=False), verdict, {})

    assert case.anonymized is True
    assert case.title == "сайт в нише fintech"
    assert "example.com" not in repr(case)
    assert build_case(_project(), verdict, {}).title == "example.com"


def test_empty_work_volume_leaves_the_block_out() -> None:
    """E4: объём работ по ТЗ необязателен — «0 ссылок» было бы выдумкой."""
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})

    assert build_case(_project(work_volume=None), verdict, {}).work_volume is None
    assert build_case(_project(work_volume=120), verdict, {}).work_volume == 120


def test_metric_present_only_at_the_end_is_not_a_change() -> None:
    """E5: сравнивать не с чем — метрики в кейсе нет, ноль не подставляется."""
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0, "refdomains": 40.0})

    case = build_case(_project(), verdict, {})

    assert case.change(Metric.REFDOMAINS.value) is None
    assert [change.subject for change in case.changes] == [Metric.ORG_TRAFFIC.value]


def test_keywords_total_needs_all_five_buckets() -> None:
    """E6: сумма четырёх корзин выглядит как число ключей, но занижает его (L30)."""
    buckets = {
        "kw_top3": 10.0,
        "kw_top4_10": 20.0,
        "kw_top11_20": 30.0,
        "kw_top21_50": 40.0,
        "kw_top51_plus": 50.0,
    }
    full = _verdict_view(buckets, {name: value * 2 for name, value in buckets.items()})
    case = build_case(_project(), full, {})
    total = case.change(KW_TOTAL)
    assert total is not None
    assert (total.before, total.after) == (150.0, 300.0)

    partial = dict(buckets)
    partial.pop("kw_top51_plus")
    halved = {name: value * 2 for name, value in partial.items()}
    case_without = build_case(_project(), _verdict_view(partial, halved), {})
    assert case_without.change(KW_TOTAL) is None


def test_case_is_deterministic() -> None:
    """E9: один и тот же вердикт даёт один и тот же кейс."""
    args = (_project(), _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0}), {})
    assert build_case(*args) == build_case(*args)


def test_metric_bought_after_the_verdict_is_reported_as_stale() -> None:
    """E7: ступень кейса покупает DR **после** классификации.

    Числа в базе есть, в точках вердикта их нет — и кейс их не покажет, потому
    что берёт числа из вердикта. Молчать об этом нельзя: кейс без строки про DR
    выглядит просто кейсом. Лечится бесплатным `classify`.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})
    traffic = {Metric.ORG_TRAFFIC: {PERIOD_START: 1000.0, PERIOD_END: 2000.0}}

    assert stale_subjects(verdict, traffic | {Metric.DR: {PERIOD_END: 60.0}}) == (Metric.DR.value,)
    assert stale_subjects(verdict, traffic) == ()


def test_malformed_verdict_point_is_an_error_not_an_empty_case() -> None:
    """E8: умолчание стёрло бы разницу между «чужая форма» и «нет данных» (L23)."""
    verdict = _verdict({"values": {"org_traffic": 1.0}}, _point(PERIOD_END, {"org_traffic": 2.0}))
    with pytest.raises(VerdictFormatError):
        VerdictView.of(verdict, VERSION)


async def _stored_project(session: AsyncSession, domain: str, **overrides: Any) -> Project:
    project = _project(domain=domain, **overrides)
    project.id = None
    session.add(project)
    await session.flush()
    return project


async def _stored_ruleset(session: AsyncSession, version: str, *, active: bool) -> Ruleset:
    ruleset = Ruleset(version=version, payload={}, is_active=active)
    session.add(ruleset)
    await session.flush()
    return ruleset


async def _stored_verdict(
    session: AsyncSession, project: Project, ruleset: Ruleset, group: Group
) -> None:
    verdict = _verdict(
        _point(PERIOD_START, {"org_traffic": 1000.0}),
        _point(PERIOD_END, {"org_traffic": 2000.0}),
        group,
    )
    verdict.project_id, verdict.ruleset_id = project.id, ruleset.id
    session.add(verdict)
    await session.flush()


async def test_four_outcomes_are_counted_separately(db_session: AsyncSession) -> None:
    """E1: кейс положен good и medium; остальные три исхода различаются.

    Слить их в «кейса нет» дёшево и неверно: «не положен», «данных не хватило» и
    «вердикта нет» ведут к разным действиям (уроки L32 и L34).
    """
    ruleset = await _stored_ruleset(db_session, VERSION, active=True)
    for domain, group in (
        ("good.example", Group.GOOD),
        ("medium.example", Group.MEDIUM),
        ("poor.example", Group.POOR),
        ("thin.example", Group.INSUFFICIENT_DATA),
    ):
        project = await _stored_project(db_session, domain)
        await _stored_verdict(db_session, project, ruleset, group)
    await _stored_project(db_session, "fresh.example")

    report = await build_cases(db_session)

    assert len(report.by_outcome(CaseOutcome.BUILT)) == 2
    assert [item.domain for item in report.by_outcome(CaseOutcome.NOT_ELIGIBLE)] == ["poor.example"]
    assert [item.domain for item in report.by_outcome(CaseOutcome.INSUFFICIENT_DATA)] == [
        "thin.example"
    ]
    assert [item.domain for item in report.by_outcome(CaseOutcome.NO_VERDICT)] == ["fresh.example"]
    assert "данных не хватило: 1" in "\n".join(report.as_lines())


async def test_case_follows_the_verdict_version_not_the_active_one(
    db_session: AsyncSession,
) -> None:
    """E10: кейс объясняется порогами, по которым его вынесли."""
    old = await _stored_ruleset(db_session, "2026-08-A", active=False)
    await _stored_ruleset(db_session, "2026-09-B", active=True)
    project = await _stored_project(db_session, "good.example")
    await _stored_verdict(db_session, project, old, Group.GOOD)
    db_session.add(
        MetricPoint(
            project_id=project.id,
            metric=Metric.ORG_TRAFFIC,
            point_date=PERIOD_START,
            value=1000.0,
            source=MetricSource.FIXTURE,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()

    by_active = await build_cases(db_session)
    by_old = await build_cases(db_session, version="2026-08-A")

    assert by_active.by_outcome(CaseOutcome.NO_VERDICT)[0].domain == "good.example"
    built = by_old.by_outcome(CaseOutcome.BUILT)
    assert built[0].case is not None
    assert built[0].case.ruleset_version == "2026-08-A"
    assert (await db_session.execute(select(Verdict))).scalars().all() != []
