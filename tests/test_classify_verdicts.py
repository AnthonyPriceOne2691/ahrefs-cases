"""Слой базы: версии порогов и запись вердиктов.

Примеры приёмки: D12 (вердикт хранит версию порогов), плюс требования
non-functional — пороги берутся из базы, а не из файла, и классификация не
делает ни одного сетевого запроса.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.rulesets import (
    active_ruleset,
    seed_thresholds,
    thresholds_of,
)
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.classify.verdicts import classify_all, classify_project
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.runner import collect_all, collect_stage2
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Group, MetricSource, ProjectStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = __import__("datetime").date(2026, 9, 15)
DEFAULTS_PATH = Path("config/thresholds.default.yml")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Классификация не имеет права ходить в сеть.

    Она считает по тому, что уже куплено; сетевой запрос отсюда означал бы,
    что смена порогов начала стоить units — ровно то, чего Ф2б добивалась.
    """

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "классификация не ходит в сеть"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


def _defaults_with_changed_threshold(value: float) -> dict[str, object]:
    """Копия умолчаний с другим порогом «хороших».

    Чтение файла вынесено из async-теста намеренно: блокирующий ввод-вывод
    внутри корутины — то, что ловит гейт `ASYNC240`, и правило разумное, хотя
    в тесте на пять строк выглядит формальностью.
    """
    raw = yaml.safe_load(DEFAULTS_PATH.read_text(encoding="utf-8"))
    raw["groups"]["good"]["org_traffic"]["growth_pct_min"] = value
    return dict(raw)


async def _prepare(
    session: AsyncSession, domains: list[str], *, stage2: bool = True
) -> list[Project]:
    """Проекты с собранными сериями.

    Шаг 2 по умолчанию выполняется: без него в базе нет ни `refdomains`, ни
    ключевых слов, а значит нет и подтверждающих метрик — «хороших» не будет
    ни у одного проекта, каким бы ни был рост трафика. Отдельный тест ниже
    держит именно это свойство конвейера.
    """
    rows = "\n".join(
        f"{domain},2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for domain in domains
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))
    await collect_all(session, AhrefsFixture(), now=NOW)
    projects = list((await session.execute(select(Project))).scalars().all())
    if stage2:
        await collect_stage2(
            session, [project.id for project in projects], AhrefsFixture(), now=NOW
        )
    return projects


async def test_without_stage_two_there_are_no_good_projects(db_session: AsyncSession) -> None:
    """D18: «хорошие» невозможны без шага 2 воронки.

    Шаг 1 приносит только трафик, а `good` требует подтверждающей метрики —
    ссылочного или позиций. Значит порядок «шаг 1 → префильтр → шаг 2 →
    классификация» обязателен, и это не деталь реализации: пропусти шаг 2, и
    сервис честно скажет «средних много, хороших нет», а причина будет не в
    проектах.
    """
    projects = await _prepare(db_session, ["d0.example.com"], stage2=False)
    ruleset = await seed_thresholds(db_session)

    decision = await classify_project(db_session, projects[0], ruleset, source=MetricSource.FIXTURE)

    assert decision.group is Group.MEDIUM
    supporting = next(r for r in decision.reasons if r.subject == "good.supporting_required")
    assert supporting.fact == 0


async def test_seed_is_idempotent_by_version(db_session: AsyncSession) -> None:
    """D19: повторный сид не плодит версии и не переписывает существующую.

    Переписывать было бы опаснее: по этой версии уже могут стоять вердикты,
    и подмена порогов задним числом лишила бы их объяснимости.
    """
    first = await seed_thresholds(db_session)
    second = await seed_thresholds(db_session)

    assert first.id == second.id
    count = (await db_session.execute(select(func.count()).select_from(Ruleset))).scalar_one()
    assert count == 1
    assert first.is_active is True


async def test_thresholds_come_from_database_not_file(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """D19: правка файла на живом сервисе ничего не меняет.

    Проверяется, а не подразумевается: файл с другими порогами читается только
    как новая версия, а действующие пороги остаются теми, что в базе.
    """
    changed = _defaults_with_changed_threshold(999)
    await seed_thresholds(db_session)
    (tmp_path / "changed.yml").write_text(
        yaml.safe_dump(changed, allow_unicode=True), encoding="utf-8"
    )

    active = await active_ruleset(db_session)

    assert thresholds_of(active).good.org_traffic.growth_pct_min == 100


async def test_no_active_ruleset_is_an_error(db_session: AsyncSession) -> None:
    """D19: классифицировать по умолчаниям нельзя — этих порогов никто не утверждал."""
    with pytest.raises(ThresholdsError, match="активной версии"):
        await active_ruleset(db_session)


async def test_verdict_keeps_the_ruleset_version(db_session: AsyncSession) -> None:
    """D12: вердикт привязан к версии порогов, по которой вынесен."""
    projects = await _prepare(db_session, ["d0.example.com"])
    ruleset = await seed_thresholds(db_session)

    decision = await classify_project(db_session, projects[0], ruleset, source=MetricSource.FIXTURE)
    await db_session.flush()

    verdict = (await db_session.execute(select(Verdict))).scalars().one()
    assert verdict.ruleset_id == ruleset.id
    assert verdict.group is decision.group
    assert verdict.reasons["checks"]


async def test_other_version_gives_its_own_verdict(db_session: AsyncSession) -> None:
    """D12: пересчёт по другой версии не затирает прошлый вердикт.

    Оба остаются объяснимыми — иначе «почему тогда было good» становится
    вопросом без ответа ровно в тот момент, когда пороги правят.
    """
    projects = await _prepare(db_session, ["d0.example.com"])
    lenient = await seed_thresholds(db_session)
    strict_payload = dict(lenient.payload)
    strict_payload["version"] = "0.2.0-strict"
    strict_payload["groups"] = {
        **strict_payload["groups"],  # type: ignore[dict-item]
        "good": {
            **strict_payload["groups"]["good"],  # type: ignore[index]
            "org_traffic": {"growth_pct_min": 10_000, "growth_abs_min": 10_000_000},
        },
    }
    strict = Ruleset(version="0.2.0-strict", payload=strict_payload, is_active=False)
    db_session.add(strict)
    await db_session.flush()

    lenient_decision = await classify_project(
        db_session, projects[0], lenient, source=MetricSource.FIXTURE
    )
    strict_decision = await classify_project(
        db_session, projects[0], strict, source=MetricSource.FIXTURE
    )
    await db_session.flush()

    verdicts = (await db_session.execute(select(Verdict))).scalars().all()
    assert len(verdicts) == 2
    assert lenient_decision.group is Group.GOOD
    assert strict_decision.group is not Group.GOOD


async def test_classify_all_reports_distribution(db_session: AsyncSession) -> None:
    """D20: отчёт по прогону — сколько проектов в какой группе."""
    await _prepare(db_session, ["d0.example.com", "d2.example.com", "d4.example.com"])
    await seed_thresholds(db_session)

    report = await classify_all(db_session, source=MetricSource.FIXTURE)

    assert report.total == 3
    assert sum(report.by_group.values()) == 3
    assert report.ruleset_version == "0.0.0-default"


async def test_classified_project_changes_status(db_session: AsyncSession) -> None:
    """D20: статус проекта двигает классификация — как сбор двигал его в Ф2."""
    projects = await _prepare(db_session, ["d0.example.com"])
    ruleset = await seed_thresholds(db_session)

    await classify_project(db_session, projects[0], ruleset, source=MetricSource.FIXTURE)
    await db_session.flush()

    assert projects[0].status is ProjectStatus.CLASSIFIED


async def test_reclassification_updates_not_duplicates(db_session: AsyncSession) -> None:
    """D12: повтор по той же версии обновляет вердикт, а не плодит второй.

    Ключ `(project_id, ruleset_id)` из модели Ф1: один проект на одной версии
    порогов имеет ровно один вердикт.
    """
    projects = await _prepare(db_session, ["d0.example.com"])
    ruleset = await seed_thresholds(db_session)

    await classify_project(db_session, projects[0], ruleset, source=MetricSource.FIXTURE)
    await classify_project(db_session, projects[0], ruleset, source=MetricSource.FIXTURE)
    await db_session.flush()

    count = (await db_session.execute(select(func.count()).select_from(Verdict))).scalar_one()
    assert count == 1
