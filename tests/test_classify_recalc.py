"""Пересчёт вердиктов по версии порогов.

Примеры приёмки поставки `f3b-recalc`: E1 (прошлые вердикты остаются), E4
(активна ровно одна версия), E5 (повтор обновляет, а не удваивает), E6 (ни
одного HTTP), E7 (несуществующая версия), E9 (нехватка купленных месяцев),
E10 (хватило — молчим).

Версии порогов собираются **в тесте**, а не читаются из порогов заказчика:
клиентский файл по варианту D вне репозитория, и тест, стоящий на нём, зелёный
только на машине автора (урок L21). Отличаются версии настолько, чтобы группа
менялась заведомо, а не по случайности шума (урок L19).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify import coverage as coverage_module
from ahrefs_cases.classify.recalc import activate, recalc, ruleset_by_version
from ahrefs_cases.classify.rulesets import seed_thresholds, thresholds_of
from ahrefs_cases.classify.thresholds import ThresholdsError, load_seed
from ahrefs_cases.classify.verdicts import classify_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
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
    """E6: любой HTTP-запрос в этих тестах — падение.

    Смена порогов обязана быть бесплатной: ради этого классификация и отделена
    от сбора. Проверяется не словами в докстринге, а падающим транспортом.
    """

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "пересчёт не имеет права обращаться к Ahrefs"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


async def _project(session: AsyncSession, domain: str) -> Project:
    row = (
        f"{domain},{PERIOD_START.isoformat()},{PERIOD_END.isoformat()},"
        "fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (
        await session.execute(select(Project).where(Project.domain == domain))
    ).scalars().one()


async def _series(session: AsyncSession, project: Project, values: dict[date, float]) -> None:
    for month, value in values.items():
        session.add(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=month,
                value=value,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await session.flush()


def _growing() -> dict[date, float]:
    """Ровный рост вдвое за год: группа заведомо не на границе порога."""
    return {date(2025, month, 1): 1000.0 + 100.0 * (month - 1) for month in range(1, 13)}


async def _ruleset(session: AsyncSession, version: str, **windows: int) -> Ruleset:
    """Версия порогов с изменёнными окнами. Пороги групп — из нейтральных умолчаний."""
    payload = load_seed().model_dump(mode="json")
    payload["version"] = version
    payload["windows"].update(windows)
    ruleset = Ruleset(version=version, payload=payload, is_active=False, note="тестовая версия")
    session.add(ruleset)
    await session.flush()
    return ruleset


async def test_recalc_keeps_the_previous_verdict(db_session: AsyncSession) -> None:
    """E1: вердикты новой версии появились, вердикты старой остались.

    Ключ `(project_id, ruleset_id)` делает версии соседями, а не заменой друг
    друга. Через полгода вопрос «почему тогда было good» обязан иметь ответ —
    иначе калибровка стирает собственную историю.
    """
    project = await _project(db_session, "keeps.example.com")
    await _series(db_session, project, _growing())
    await seed_thresholds(db_session)
    await classify_all(db_session)
    first = await _ruleset(db_session, "2026-09-B", point_a_months=3)

    report = await recalc(db_session, first.version)

    verdicts = (
        await db_session.execute(select(Verdict).where(Verdict.project_id == project.id))
    ).scalars().all()
    assert report.recalculated == 1
    assert len({verdict.ruleset_id for verdict in verdicts}) == 2, "две версии, два вердикта"


async def test_activation_leaves_exactly_one_active(db_session: AsyncSession) -> None:
    """E4: активна ровно одна версия, вердикты прежней не тронуты."""
    project = await _project(db_session, "activate.example.com")
    await _series(db_session, project, _growing())
    seeded = await seed_thresholds(db_session)
    await classify_all(db_session)
    before = (
        await db_session.execute(
            select(func.count()).select_from(Verdict).where(Verdict.ruleset_id == seeded.id)
        )
    ).scalar_one()
    other = await _ruleset(db_session, "2026-09-C", point_b_months=3)

    activated = await activate(db_session, other.version)

    active = (
        await db_session.execute(select(Ruleset).where(Ruleset.is_active.is_(True)))
    ).scalars().all()
    after = (
        await db_session.execute(
            select(func.count()).select_from(Verdict).where(Verdict.ruleset_id == seeded.id)
        )
    ).scalar_one()
    assert [ruleset.id for ruleset in active] == [activated.id]
    assert after == before, "активация не переписывает прошлые вердикты"


async def test_repeated_recalc_updates_instead_of_duplicating(db_session: AsyncSession) -> None:
    """E5: повторный пересчёт по той же версии обновляет вердикт, а не удваивает."""
    project = await _project(db_session, "twice.example.com")
    await _series(db_session, project, _growing())
    ruleset = await _ruleset(db_session, "2026-09-D")

    await recalc(db_session, ruleset.version)
    await recalc(db_session, ruleset.version)

    count = (
        await db_session.execute(
            select(func.count()).select_from(Verdict).where(Verdict.ruleset_id == ruleset.id)
        )
    ).scalar_one()
    assert count == 1


async def test_recalc_touches_no_network(db_session: AsyncSession) -> None:
    """E6: пересчёт по десяти проектам не делает ни одного HTTP-запроса.

    Транспорт подменён падающим в фикстуре: любой запрос уронил бы тест. В этом
    и был смысл отделять классификацию от сбора — смена порогов бесплатна.
    """
    for index in range(10):
        project = await _project(db_session, f"free{index}.example.com")
        await _series(db_session, project, _growing())
    ruleset = await _ruleset(db_session, "2026-09-E")

    report = await recalc(db_session, ruleset.version)

    assert report.total == 10
    assert report.recalculated == 10
    assert sum(report.by_group.values()) == 10


async def test_unknown_version_lists_the_known_ones(db_session: AsyncSession) -> None:
    """E7: несуществующая версия — ошибка со списком доступных, а не пустой результат.

    Пустота на опечатку читается как «я поправил пороги, ничего не изменилось»,
    и на калибровке это самый дорогой способ потерять час.
    """
    await _ruleset(db_session, "2026-09-F")

    with pytest.raises(ThresholdsError) as excinfo:
        await ruleset_by_version(db_session, "2026-09-НЕТ")

    assert "2026-09-F" in str(excinfo.value), "в ошибке перечислены доступные версии"


async def test_version_asking_unbought_months_is_skipped(db_session: AsyncSession) -> None:
    """E9: версия просит месяцы до старта работ, которых никто не покупал.

    С 11.09.2026 запас до старта берётся ровно тот, что просит версия порогов в
    момент **сбора**. Включить `pre_start_baseline_months` на калибровке —
    значит попросить месяцы, которых нет в базе. Точка усреднила бы то, что
    есть, и вердикт по половине окна выглядел бы настоящим: спорили бы с
    порогом вместо того, чтобы докупить данные.
    """
    project = await _project(db_session, "baseline.example.com")
    await _series(db_session, project, _growing())
    ruleset = await _ruleset(db_session, "2026-09-G", pre_start_baseline_months=3)

    report = await recalc(db_session, ruleset.version)

    assert report.recalculated == 0
    assert [item.domain for item in report.skipped] == ["baseline.example.com"]
    assert "baseline до старта" in report.skipped[0].reason
    assert "2024-10" in report.skipped[0].reason, "месяцы названы, а не сосчитаны"
    written = (
        await db_session.execute(
            select(func.count()).select_from(Verdict).where(Verdict.ruleset_id == ruleset.id)
        )
    ).scalar_one()
    assert written == 0, "вердикт по неполному окну не выдаётся вовсе"


async def test_wider_window_inside_bought_history_is_silent(db_session: AsyncSession) -> None:
    """E10: окно шире прежнего, но внутри купленной истории — пересчёт молчит.

    Предупреждение, которое срабатывает и когда всё в порядке, перестаёт быть
    предупреждением. История шага 1 собирается целиком, поэтому расширение окна
    точки внутри периода данных не требует ничего докупать.
    """
    project = await _project(db_session, "wide.example.com")
    await _series(db_session, project, _growing())
    ruleset = await _ruleset(db_session, "2026-09-H", point_a_months=6, point_b_months=6)

    report = await recalc(db_session, ruleset.version)

    assert report.skipped == []
    assert report.recalculated == 1
    assert "пропущено 0" in "\n".join(report.as_lines())


async def test_empty_history_gets_a_verdict_not_a_skip(db_session: AsyncSession) -> None:
    """E9 наоборот: у домена нет истории вовсе — это вердикт, а не нехватка.

    Два состояния, которые легко слить: «данных не покупали» и «данных нет и не
    будет». Первое чинится деньгами, второе — решением человека о проекте.
    Слить их значит показать заказчику ложную причину.
    """
    project = await _project(db_session, "silent.example.com")
    ruleset = await _ruleset(db_session, "2026-09-I", pre_start_baseline_months=3)

    report = await recalc(db_session, ruleset.version)

    assert report.skipped == []
    assert report.by_group.get(Group.INSUFFICIENT_DATA) == 1


def test_hole_inside_history_is_not_a_coverage_gap() -> None:
    """Различитель к E9: дыра внутри собранного отрезка — не нехватка покупки.

    О ней уже судит правило достоверности серии (`max_series_gap_months`), и
    вердикт `insufficient_data` по ней законен. Посчитать её нехваткой значит
    потерять законный вердикт.
    """
    windows = thresholds_of(
        Ruleset(version="x", payload=load_seed().model_dump(mode="json"), is_active=False)
    ).windows
    months = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 11, 1), date(2025, 12, 1)]

    gap = coverage_module.gap(
        months, period_start=PERIOD_START, period_end=PERIOD_END, windows=windows
    )

    assert gap.is_empty
