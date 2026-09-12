"""Предпросмотр «кто сменит группу».

Примеры приёмки поставки `f3b-preview`: E2 (ничего не записано), E3 (тот же
ответ, что у пересчёта), E8 (изменений нет — словами), E8a (проект без
вердикта), E9b (нехватка данных показана отдельно).

Версии порогов собираются в тесте, а не читаются из клиентского файла (урок
L21), и отличаются настолько, чтобы группа менялась заведомо, а не по шуму на
пороге (урок L19).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import recalc
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.thresholds import load_seed
from ahrefs_cases.classify.verdicts import classify_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource, ProjectStatus
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2025, 12, 1)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Предпросмотр не имеет права обращаться к Ahrefs: смена порогов бесплатна."""

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "предпросмотр не имеет права обращаться к Ahrefs"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


async def _project(session: AsyncSession, domain: str) -> Project:
    row = (
        f"{domain},{PERIOD_START.isoformat()},{PERIOD_END.isoformat()},"
        "fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (await session.execute(select(Project).where(Project.domain == domain))).scalars().one()


async def _series(session: AsyncSession, project: Project, growth: float) -> None:
    """Ровный рост в `growth` раз за год — форма заведомо не на границе порога."""
    step = (1000.0 * growth - 1000.0) / 11
    for index, month in enumerate(range(1, 13)):
        session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=1000.0 + step * index,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await session.flush()


async def _ruleset(session: AsyncSession, version: str, **overrides: object) -> Ruleset:
    """Версия порогов: пороги групп можно подвинуть, чтобы группа сменилась заведомо."""
    payload = load_seed().model_dump(mode="json")
    payload["version"] = version
    for key, value in overrides.items():
        if key == "medium_growth_pct":
            payload["groups"]["medium"]["org_traffic"]["growth_pct_min"] = value
        elif key == "medium_supporting":
            payload["groups"]["medium"]["supporting_required"] = value
        elif key == "baseline_months":
            payload["windows"]["pre_start_baseline_months"] = value
    ruleset = Ruleset(version=version, payload=payload, is_active=False, note="тестовая версия")
    session.add(ruleset)
    await session.flush()
    return ruleset


async def _classified(session: AsyncSession, domain: str, growth: float) -> Project:
    project = await _project(session, domain)
    await _series(session, project, growth)
    await seed_thresholds(session)
    await classify_all(session, source=MetricSource.FIXTURE)
    return project


async def test_preview_writes_nothing(db_session: AsyncSession) -> None:
    """E2: предпросмотр показывает «было → стало» и **не пишет в базу**.

    Проверяется счётом строк и статусов до и после, а не отсутствием вызова
    записи в коде: «не пишет» — свойство поведения, и читать его надо из базы.
    """
    project = await _classified(db_session, "quiet.example.com", growth=1.5)
    softer = await _ruleset(db_session, "2026-09-P1", medium_growth_pct=5.0)
    before_rows = (await db_session.execute(select(func.count()).select_from(Verdict))).scalar_one()
    before_status = project.status

    report = await preview(db_session, softer.version, source=MetricSource.FIXTURE)

    after_rows = (await db_session.execute(select(func.count()).select_from(Verdict))).scalar_one()
    assert after_rows == before_rows, "предпросмотр не создал ни одной строки"
    assert project.status is before_status, "статус проекта не тронут"
    assert report.total == 1
    assert "ничего не записано" in report.as_lines()[0]


async def test_preview_matches_what_recalc_will_do(db_session: AsyncSession) -> None:
    """E3: предпросмотр даёт тот же ответ, что даст пересчёт.

    Не «похожий», а тот же: оба идут через `verdicts.evaluate`. Если однажды
    разойдутся — заказчик утвердит порог по предпросмотру и получит другие
    группы, а заметит это на кейсах.
    """
    await _classified(db_session, "same1.example.com", growth=1.5)
    project2 = await _project(db_session, "same2.example.com")
    await _series(db_session, project2, growth=1.05)
    await classify_all(db_session, source=MetricSource.FIXTURE)
    version = await _ruleset(db_session, "2026-09-P2", medium_growth_pct=20.0)

    shown = await preview(db_session, version.version, source=MetricSource.FIXTURE)
    await recalc(db_session, version.version, source=MetricSource.FIXTURE)

    stored = {
        row.domain: row.group
        for row in (
            await db_session.execute(
                select(Project.domain, Verdict.group)
                .join(Verdict, Verdict.project_id == Project.id)
                .where(Verdict.ruleset_id == version.id)
            )
        ).all()
    }
    previewed = {change.domain: change.after for change in (*shown.changes, *shown.first_time)}
    for domain, group in previewed.items():
        assert stored[domain] is group, f"предпросмотр и пересчёт разошлись на {domain}"
    assert len(stored) == shown.total - len(shown.missing_data)


async def test_no_changes_is_said_in_words(db_session: AsyncSession) -> None:
    """E8: если ничего не меняется — так и сказано.

    «Изменений нет» и «нечего показывать» читаются одинаково, а значат разное:
    второе может означать опечатку в версии или пустую базу.
    """
    await _classified(db_session, "stable.example.com", growth=1.5)
    same = await _ruleset(db_session, "2026-09-P3")

    report = await preview(db_session, same.version, source=MetricSource.FIXTURE)

    assert report.changes == ()
    assert report.unchanged == 1
    assert "изменений нет" in "\n".join(report.as_lines())


async def test_project_without_verdict_is_shown_not_hidden(db_session: AsyncSession) -> None:
    """E8a: проект без вердикта показан как «нет вердикта → группа».

    Спрятать его среди «без изменений» значит не заметить, что часть списка
    вообще не классифицирована, — а на калибровке это половина разбора.
    """
    await seed_thresholds(db_session)
    fresh = await _project(db_session, "fresh.example.com")
    await _series(db_session, fresh, growth=1.5)
    version = await _ruleset(db_session, "2026-09-P4")

    report = await preview(db_session, version.version, source=MetricSource.FIXTURE)

    assert report.changes == ()
    assert [change.domain for change in report.first_time] == ["fresh.example.com"]
    assert report.first_time[0].before is None
    assert "нет вердикта →" in "\n".join(report.as_lines())


async def test_missing_data_is_shown_apart_from_unchanged(db_session: AsyncSession) -> None:
    """E9b: проект, которому версия просит непокупленные месяцы, показан отдельно.

    Он не «не изменится» — его этой версией считать нечем. Слить эти два
    состояния значит показать «всё в порядке» там, где не хватает данных
    (урок L30).
    """
    await _classified(db_session, "gap.example.com", growth=1.5)
    demanding = await _ruleset(db_session, "2026-09-P5", baseline_months=3)

    report = await preview(db_session, demanding.version, source=MetricSource.FIXTURE)

    assert report.changes == ()
    assert report.unchanged == 0, "проект с нехваткой не считается неизменившимся"
    assert [item.domain for item in report.missing_data] == ["gap.example.com"]
    assert "2024-10" in report.missing_data[0].reason
    assert "не хватает данных" in "\n".join(report.as_lines())


async def test_directions_count_projects_and_are_stable(db_session: AsyncSession) -> None:
    """Сводка «откуда куда» считает проекты и не прыгает между запусками.

    Счёт по парам групп вместо проектов дал бы число, которого нет ни у кого на
    экране (урок L13), а нестабильный порядок сделал бы два вывода калибровки
    несравнимыми глазами.
    """
    for index in range(3):
        project = await _project(db_session, f"move{index}.example.com")
        await _series(db_session, project, growth=1.5)
    await seed_thresholds(db_session)
    await classify_all(db_session, source=MetricSource.FIXTURE)
    strict = await _ruleset(db_session, "2026-09-P6", medium_growth_pct=200.0)

    first = await preview(db_session, strict.version, source=MetricSource.FIXTURE)
    second = await preview(db_session, strict.version, source=MetricSource.FIXTURE)

    assert sum(first.directions().values()) == len(first.changes)
    assert list(first.directions()) == list(second.directions())
    assert [change.domain for change in first.changes] == [
        change.domain for change in second.changes
    ]


async def test_status_of_projects_stays_untouched(db_session: AsyncSession) -> None:
    """E2, вторая половина: предпросмотр не двигает статусы проектов.

    `store` ставит `ProjectStatus.CLASSIFIED`; предпросмотр обязан оставить
    статус прежним, иначе воронка шага 2 увидит проект классифицированным по
    версии, которую никто не применял.
    """
    project = await _project(db_session, "status.example.com")
    await _series(db_session, project, growth=1.5)
    version = await _ruleset(db_session, "2026-09-P7")
    before = project.status

    await preview(db_session, version.version, source=MetricSource.FIXTURE)

    assert project.status is before, "статус остался тем, каким был до предпросмотра"
    assert project.status is not ProjectStatus.CLASSIFIED


async def test_preview_after_recalc_reports_no_changes(db_session: AsyncSession) -> None:
    """Устойчивость E3: если версию уже применили и активировали — изменений нет.

    Проверяет, что «было» берётся по активной версии, а не по последнему
    вердикту во времени: иначе после активации предпросмотр той же версии
    показывал бы изменения, которых нет.
    """
    await _classified(db_session, "applied.example.com", growth=1.5)
    version = await _ruleset(db_session, "2026-09-P8", medium_growth_pct=20.0)
    await recalc(db_session, version.version, source=MetricSource.FIXTURE)
    for ruleset in (await db_session.execute(select(Ruleset))).scalars().all():
        ruleset.is_active = ruleset.id == version.id
    await db_session.flush()

    report = await preview(db_session, version.version, source=MetricSource.FIXTURE)

    assert report.changes == ()
    assert report.first_time == ()
    assert report.unchanged == 1
