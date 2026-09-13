"""Три пути к одному расчёту отвечают одинаково.

Вердикт считают трое: `classify` (пишет), `preview` (показывает, что будет) и
`recalc` (перекладывает на другую версию порогов). Живая проверка 13.09.2026
застала их спорящими об одном проекте: «good» / «не хватает данных» / «пропущен,
вердикт не записан». Правило покрытия стояло в обёртке `evaluate`, и короткий
путь его не видел.

Цена расхождения — калибровка: она вся состоит из «поменяли порог → пересчитали
→ сверили с экспертом», и на этом шаге девять проектов из девятнадцати остались
без вердикта, а экран об этом промолчал.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import recalc
from ahrefs_cases.classify.rulesets import active_ruleset, seed_thresholds
from ahrefs_cases.classify.verdicts import classify_all, compute_verdict
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project

_SOURCE = MetricSource.FIXTURE


async def _project_missing_its_first_month(session: AsyncSession) -> Project:
    """Проект, у которого нет первого месяца периода работ.

    Так выглядит обычный живой случай: работы начались в июне, а Ahrefs знает
    домен с июля. На стенде 13.09.2026 таких было девять из девятнадцати.
    """
    project = Project(
        domain="поздняя-история.example",
        niche="фин",
        geo="US",
        service_type="seo",
        period_start=date(2024, 6, 1),
        period_end=date(2025, 12, 1),
        client="Заказчик",
        owner="владелец",
        publishable=True,
    )
    session.add(project)
    await session.flush()

    value = 1000.0
    for index in range(18):  # с 2024-07 по 2025-12 — на месяц позже старта
        month = date(2024 + (6 + index) // 12, (6 + index) % 12 + 1, 1)
        session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=month,
                value=value * (1 + index * 0.12),
                source=_SOURCE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await session.flush()
    return project


@pytest.fixture
async def late_history(db_session: AsyncSession) -> Project:
    await seed_thresholds(db_session)
    return await _project_missing_its_first_month(db_session)


async def test_classification_and_preview_agree(
    db_session: AsyncSession, late_history: Project
) -> None:
    """E1: классификация и предпросмотр говорят об одном проекте одно и то же.

    Раньше `classify` выдавал группу, а `preview` объявлял «не хватает данных:
    точка А 2024-06» — тот же проект, те же пороги, тот же источник.
    """
    ruleset = await active_ruleset(db_session)
    await classify_all(db_session, source=_SOURCE)
    computed = await compute_verdict(db_session, late_history, ruleset, source=_SOURCE)

    shown = await preview(db_session, ruleset.version, source=_SOURCE)
    missing = [item.domain for item in shown.missing_data]

    assert computed.decision.group is not Group.INSUFFICIENT_DATA, (
        "месяц внутри периода, которого нет у Ahrefs, — не повод отказать в вердикте"
    )
    assert late_history.domain not in missing, "предпросмотр обязан отвечать так же"


async def test_recalc_leaves_no_project_without_a_verdict(
    db_session: AsyncSession, late_history: Project
) -> None:
    """E4: после пересчёта у каждого проекта есть вердикт этой версии.

    Пропуск без записи означал, что карточка показывает группу, посчитанную
    **другой** версией порогов, и человек об этом не знает.
    """
    ruleset = await active_ruleset(db_session)

    report = await recalc(db_session, ruleset.version, source=_SOURCE)

    assert report.recalculated == report.total
    assert report.total >= 1


async def test_truncated_history_is_said_out_loud(
    db_session: AsyncSession, late_history: Project
) -> None:
    """E2: усечённое окно точки названо справочной записью, а не молчанием.

    «Рост 151 %» по одному месяцу из двух и по двум из двух — разные
    утверждения, и человеку нужно знать, какое перед ним. Пока правило покрытия
    просто **запрещало** такой вердикт, молчания не было заметно; сняв запрет,
    мы обязаны сказать об этом словами.
    """
    ruleset = await active_ruleset(db_session)

    computed = await compute_verdict(db_session, late_history, ruleset, source=_SOURCE)

    subjects = [reason.subject for reason in computed.decision.reasons]
    note = next(r for r in computed.decision.reasons if r.subject == "point_a_months_used")

    assert "point_a_months_used" in subjects
    assert note.fact == 1.0, "точка А посчитана по одному месяцу из двух"
    assert note.decisive is False, "справочная запись группу не меняет"


async def test_full_coverage_behaves_exactly_as_before(db_session: AsyncSession) -> None:
    """E5: проект с полным покрытием не замечает этой поставки.

    Проверка на то, что правило сузилось, а не выключилось: у проекта,
    покрытого целиком, ни одной новой записи в объяснении не появляется.
    """
    await seed_thresholds(db_session)
    project = Project(
        domain="полное-покрытие.example",
        niche="фин",
        geo="US",
        service_type="seo",
        period_start=date(2024, 7, 1),
        period_end=date(2025, 12, 1),
        client="Заказчик",
        owner="владелец",
        publishable=True,
    )
    db_session.add(project)
    await db_session.flush()
    for index in range(18):
        month = date(2024 + (6 + index) // 12, (6 + index) % 12 + 1, 1)
        db_session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=month,
                value=1000.0 * (1 + index * 0.12),
                source=_SOURCE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await db_session.flush()
    ruleset = await active_ruleset(db_session)

    computed = await compute_verdict(db_session, project, ruleset, source=_SOURCE)

    subjects = [reason.subject for reason in computed.decision.reasons]
    assert "history_truncated" not in subjects
    assert "unbought_months" not in subjects
    assert "point_a_months_used" not in subjects
    assert computed.gap.is_empty
