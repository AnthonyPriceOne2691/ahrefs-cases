"""Диагностика «плохих» и отказ нереализованной нормализации.

Примеры приёмки поставки `f3v-diagnose`: E1 (падение), E2 (слабый рост), E3
(плоская серия), E4 (позиции и ссылки не покупались), E5 (потерянные домены),
E6 (ни сети, ни записи), E7 (список со стабильным порядком), E8 (ненулевая
нормализация отказывает во всех трёх путях).

Серии здесь задаются числами прямо в тесте: диагноз обязан воспроизводиться
человеком по этим числам, иначе на калибровке с ним нечем спорить.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.diagnose import (
    TrafficVerdict,
    diagnose_domain,
    diagnose_poor,
    diagnose_traffic,
)
from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import recalc
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.thresholds import ThresholdsError, load_seed, parse
from ahrefs_cases.classify.verdicts import classify_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Metric, MetricSource
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
    """E6: диагностика не имеет права обращаться к Ahrefs."""

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        message = "диагностика не имеет права обращаться к Ahrefs"
        raise AssertionError(message)

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


def _series(values: list[float], metric: Metric = Metric.ORG_TRAFFIC) -> dict:
    return {metric: {date(2025, month, 1): value for month, value in enumerate(values, start=1)}}


async def _project(session: AsyncSession, domain: str) -> Project:
    row = (
        f"{domain},{PERIOD_START.isoformat()},{PERIOD_END.isoformat()},"
        "fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{row}\n", origin="test"))
    return (await session.execute(select(Project).where(Project.domain == domain))).scalars().one()


async def _points(
    session: AsyncSession, project: Project, values: list[float], metric: Metric
) -> None:
    for month, value in enumerate(values, start=1):
        session.add(
            MetricPoint(
                project_id=project.id,
                metric=metric,
                point_date=date(2025, month, 1),
                value=value,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await session.flush()


def test_drop_names_peak_depth_and_when_it_started() -> None:
    """E1: падение — это пик, глубина, месяц начала и длительность.

    Серия: рост до апреля (2000), потом вниз до 1200 в декабре. Человек обязан
    перепроверить вывод по этим числам: минус 40 % от пика, снижение восемь
    месяцев, началось с мая.
    """
    values = [1000, 1400, 1800, 2000, 1900, 1800, 1700, 1600, 1500, 1400, 1300, 1200]

    found = diagnose_traffic(_series([float(v) for v in values]), PERIOD_START)

    assert found.verdict is TrafficVerdict.DROPPED
    assert found.peak_at == date(2025, 4, 1)
    assert found.peak_value == 2000
    assert found.last_value == 1200
    assert found.drop_pct == pytest.approx(40.0)
    assert found.decline_months == 8
    described = found.describe()
    assert "падение с 2025-05" in described, "начало снижения — месяц ПОСЛЕ пика"
    assert "минус 40 %" in described


def test_weak_growth_is_not_called_a_drop() -> None:
    """E2: слабый рост — не падение.

    Пик в последнем месяце: назвать это падением значит отправить человека
    искать поломку в месяце, где ничего не ломалось. Диагноз другой и вопрос
    другой — «те ли работы велись».
    """
    found = diagnose_traffic(_series([1000.0 + 20 * step for step in range(12)]), PERIOD_START)

    assert found.verdict is TrafficVerdict.NO_GROWTH
    assert "падения не было" in found.describe()


def test_flat_series_is_its_own_diagnosis() -> None:
    """E3: серия без движения — третий случай, а не подвид первых двух.

    Колебание в пределах ширины шума (`FLAT_TOLERANCE_PCT`) не «рост» и не
    «падение»: чаще всего это мёртвый или технический домен, и действие по нему
    третье.
    """
    found = diagnose_traffic(_series([1000.0, 1005.0, 995.0, 1000.0] * 3), PERIOD_START)

    assert found.verdict is TrafficVerdict.FLAT
    assert "не менялся" in found.describe()


def test_months_before_the_start_are_not_counted() -> None:
    """Диагноз считается по месяцам после старта работ.

    До старта шли чужие результаты, и приписывать их этим работам нельзя ни в
    плюс, ни в минус: пик, случившийся до начала, сделал бы «падением» любой
    проект, который пришёл к нам после спада.
    """
    series = _series([5000.0, 4000.0, 1000.0, 1100.0, 1200.0, 1300.0])

    whole = diagnose_traffic(series, date(2025, 1, 1))
    after_start = diagnose_traffic(series, date(2025, 3, 1))

    assert whole.verdict is TrafficVerdict.DROPPED
    assert after_start.verdict is TrafficVerdict.NO_GROWTH


async def test_missing_stage2_data_is_said_in_words(db_session: AsyncSession) -> None:
    """E4: «позиции и ссылки не покупались» — словами и с ценой вопроса.

    Молчание читалось бы как «со ссылками всё в порядке», а это ровно тот
    случай, где ответ стоит денег: шаг 2 платится кандидатам, «плохие» в них не
    попадают (урок L30).
    """
    project = await _project(db_session, "nolinks.example.com")
    await _points(db_session, project, [2000.0, 1500.0, 1000.0], Metric.ORG_TRAFFIC)

    found = await diagnose_domain(db_session, project.domain, source=MetricSource.FIXTURE)

    assert found is not None
    assert found.refdomains.bought is False
    assert "не покупались" in found.refdomains.describe()
    assert "units" in found.refdomains.describe(), "цена вопроса названа"


async def test_lost_refdomains_are_counted(db_session: AsyncSession) -> None:
    """E5: если история ссылок есть — сказано, потеряны ли домены, числом."""
    project = await _project(db_session, "lostlinks.example.com")
    await _points(db_session, project, [2000.0, 1500.0, 1000.0], Metric.ORG_TRAFFIC)
    await _points(db_session, project, [120.0, 100.0, 80.0], Metric.REFDOMAINS)

    found = await diagnose_domain(db_session, project.domain, source=MetricSource.FIXTURE)

    assert found is not None
    assert found.refdomains.bought is True
    assert "потеряно доменов: 120 → 80" in found.refdomains.describe()


async def test_diagnose_writes_nothing(db_session: AsyncSession) -> None:
    """E6: диагностика ничего не пишет — ни вердиктов, ни статусов."""
    project = await _project(db_session, "quiet.example.com")
    await _points(db_session, project, [2000.0, 1500.0, 1000.0], Metric.ORG_TRAFFIC)
    before_rows = (await db_session.execute(select(func.count()).select_from(Verdict))).scalar_one()
    before_status = project.status

    await diagnose_domain(db_session, project.domain, source=MetricSource.FIXTURE)

    after_rows = (await db_session.execute(select(func.count()).select_from(Verdict))).scalar_one()
    assert after_rows == before_rows
    assert project.status is before_status


async def test_poor_list_is_stable_and_only_poor(db_session: AsyncSession) -> None:
    """E7: список — только «плохие» по действующей версии, порядок стабильный."""
    falling = await _project(db_session, "zzz-falling.example.com")
    await _points(db_session, falling, [2000.0, 1500.0, 1000.0, 900.0], Metric.ORG_TRAFFIC)
    also_poor = await _project(db_session, "aaa-falling.example.com")
    await _points(db_session, also_poor, [3000.0, 2000.0, 1500.0, 1000.0], Metric.ORG_TRAFFIC)
    growing = await _project(db_session, "mmm-growing.example.com")
    await _points(
        db_session, growing, [1000.0, 1500.0, 2000.0, 2600.0, 3200.0, 4000.0], Metric.ORG_TRAFFIC
    )
    await seed_thresholds(db_session)
    await classify_all(db_session, source=MetricSource.FIXTURE)

    first = await diagnose_poor(db_session, source=MetricSource.FIXTURE)
    second = await diagnose_poor(db_session, source=MetricSource.FIXTURE)

    domains = [item.domain for item in first]
    assert domains == sorted(domains), "порядок по домену, а не как вернула база"
    assert [item.domain for item in second] == domains
    assert "mmm-growing.example.com" not in domains


def test_unimplemented_normalization_refuses_to_parse() -> None:
    """E8: ненулевая нормализация отказывает, а не считается молча.

    Поле в документе порогов выглядит рабочим, а в Ф6 станет полем ввода.
    Поставив 12, заказчик увидел бы прежние группы и сделал вывод о порогах, а
    не о нереализованном блоке — и спорил бы с нами о цифрах, а не о том, что
    формулы до сих пор нет.
    """
    payload = load_seed().model_dump(mode="json")
    payload["duration"]["normalize_after_months"] = 12

    with pytest.raises(ThresholdsError) as excinfo:
        parse(payload)

    assert "не реализована" in str(excinfo.value)
    assert "формулы от заказчика нет" in str(excinfo.value)


async def test_normalization_refusal_reaches_every_path(db_session: AsyncSession) -> None:
    """E8, вторая половина: отказ виден классификации, пересчёту и предпросмотру.

    Отказ на разборе порогов, а не в одном из путей: иначе версия, которую
    отвергает классификация, спокойно прошла бы предпросмотром — и заказчик
    увидел бы «что будет», чего не будет.
    """
    project = await _project(db_session, "norm.example.com")
    await _points(db_session, project, [1000.0, 1200.0, 1400.0], Metric.ORG_TRAFFIC)
    payload = load_seed().model_dump(mode="json")
    payload["version"] = "2026-09-N"
    payload["duration"]["normalize_after_months"] = 6
    db_session.add(
        Ruleset(version="2026-09-N", payload=payload, is_active=False, note="нормализация")
    )
    await db_session.flush()

    with pytest.raises(ThresholdsError):
        await recalc(db_session, "2026-09-N", source=MetricSource.FIXTURE)
    with pytest.raises(ThresholdsError):
        await preview(db_session, "2026-09-N", source=MetricSource.FIXTURE)
