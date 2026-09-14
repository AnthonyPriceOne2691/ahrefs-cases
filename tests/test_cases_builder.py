"""Структура кейса: числа, готовые к рендеру.

Примеры приёмки поставки `case-structure`: E1 (четыре исхода), E2 (числа из
записанного вердикта), E3 (анонимность), E4 (пустой объём работ), E5 (метрика
только в точке Б), E6 («число ключей» при всех пяти корзинах), E7 (вердикт
старше данных), E8 (точка чужой формы), E9 (детерминированность), E10 (версия
порогов из вердикта).

Поставка `verdict-remembers-its-source` добавила к ним происхождение чисел: E2
(вердикт из другого источника), E3 (источник не записан), E4 (месяц докуплен в
окно после вердикта), E5 (метрика докуплена после вердикта — предупреждение, а
не отказ), E6 (обычный порядок прогона по-прежнему даёт кейсы), E8 (период
правили после классификации).

Кейс собирается **из вердикта**, поэтому большинство примеров чистые: точки
строятся в том же JSONB-виде, в каком их пишет `classify/verdicts.store`, а
серия — словарём. База нужна там, где проверяется отбор проектов, и там, где
рядом обязаны лежать ряды **двух** источников: в одном источнике совпадение
выполняется само собой, и дефект остаётся невидимым (класс урока L107).
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
    numbers_mismatch,
    stale_subjects,
)
from ahrefs_cases.cases.model import KW_TOTAL, CaseOutcome
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.thresholds import Windows, load_seed
from ahrefs_cases.classify.verdicts import classify_projects
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.runner import collect_all, collect_case_data, collect_stage2
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2025, 12, 1)
VERSION = "2026-09-A"
INTAKE_COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)


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


def _verdict(
    point_a: dict,
    point_b: dict,
    group: Group = Group.GOOD,
    source: MetricSource | None = MetricSource.FIXTURE,
) -> Verdict:
    return Verdict(
        project_id=1,
        ruleset_id=1,
        group=group,
        score=0.0,
        reasons={},
        point_a=point_a,
        point_b=point_b,
        source=source,
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
    return VerdictView.of(verdict, VERSION)


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
    """Версия порогов с настоящим содержимым: из неё сверка берёт окна точек."""
    payload = load_seed().model_dump(mode="json") | {"version": version}
    ruleset = Ruleset(version=version, payload=payload, is_active=active)
    session.add(ruleset)
    await session.flush()
    return ruleset


async def _stored_verdict(
    session: AsyncSession,
    project: Project,
    ruleset: Ruleset,
    group: Group,
    *,
    source: MetricSource | None = MetricSource.FIXTURE,
    values_a: dict[str, float] | None = None,
    values_b: dict[str, float] | None = None,
) -> None:
    verdict = _verdict(
        _point(PERIOD_START, values_a or {"org_traffic": 1000.0}),
        _point(PERIOD_END, values_b or {"org_traffic": 2000.0}),
        group,
        source,
    )
    verdict.project_id, verdict.ruleset_id = project.id, ruleset.id
    session.add(verdict)
    await session.flush()


async def _stored_points(
    session: AsyncSession,
    project: Project,
    by_month: dict[date, float],
    *,
    source: MetricSource,
    metric: Metric = Metric.ORG_TRAFFIC,
) -> None:
    """Ряд одной метрики в базе. Источник назван явно: в этом файле его как раз
    и проверяют, а умолчание сделало бы совпадение источников невидимым (L107)."""
    for month, value in by_month.items():
        session.add(
            MetricPoint(
                project_id=project.id,
                metric=metric,
                point_date=month,
                value=value,
                source=source,
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    await session.flush()


HALF_YEAR = [date(2025, month, 1) for month in range(1, 7)]
LAST_HALF = [date(2025, month, 1) for month in range(7, 13)]
MATCHING_SERIES = dict.fromkeys(HALF_YEAR, 1000.0) | dict.fromkeys(LAST_HALF, 2000.0)
"""Ряд, из которого точки вердикта (1000 → 2000) воспроизводятся при любом
окне до полугода: значение постоянно внутри каждой половины периода, поэтому
среднее по окну равно ему самому и сверка не зависит от ширины окна."""


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
        await _stored_points(db_session, project, MATCHING_SERIES, source=MetricSource.FIXTURE)
    await _stored_project(db_session, "fresh.example")

    report = await build_cases(db_session, source=MetricSource.FIXTURE)

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
    await _stored_points(db_session, project, MATCHING_SERIES, source=MetricSource.FIXTURE)

    by_active = await build_cases(db_session, source=MetricSource.FIXTURE)
    by_old = await build_cases(db_session, version="2026-08-A", source=MetricSource.FIXTURE)

    assert by_active.by_outcome(CaseOutcome.NO_VERDICT)[0].domain == "good.example"
    built = by_old.by_outcome(CaseOutcome.BUILT)
    assert built[0].case is not None
    assert built[0].case.ruleset_version == "2026-08-A"
    assert (await db_session.execute(select(Verdict))).scalars().all() != []


def test_idn_domain_reads_as_a_human_wrote_it() -> None:
    """E1/E2: в кейсе домен выглядит так, как его пишет человек, а не как ждёт API.

    В базе и в запросах к Ahrefs домен живёт каноном —
    `xn----7sbfmzvfbjddnn.example`. Сплошная проверка 13.09.2026 нашла этот
    канон в заголовке PDF и в имени файла, уходящего клиенту агентства: читается
    как ошибка сервиса. Латинский домен при этом не меняется ни на символ.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})

    idn = build_case(_project(domain="xn----7sbfmzvfbjddnn.example"), verdict, {})
    ascii_only = build_case(_project(domain="example.com"), verdict, {})

    assert idn.title == "проверка-рост.example"
    assert ascii_only.title == "example.com"


def test_broken_punycode_does_not_break_the_case() -> None:
    """E4: хост, который обратно не разбирается, показывается как есть.

    Такой приезжает из чужой системы, и уронить на нём сборку кейса хуже, чем
    показать канон: кейс не соберётся ни для кого, а причина будет неочевидной.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})

    case = build_case(_project(domain="xn--битый.example"), verdict, {})

    assert case.title == "xn--битый.example"


async def test_case_refuses_when_the_verdict_came_from_other_data(
    db_session: AsyncSession,
) -> None:
    """E2: в базе ряды двух источников, вердикт посчитан по одному из них.

    Так выглядит стенд: фикстуры пишет разработка, живые ряды приезжают
    прогоном. Числа таблицы кейса берутся из вердикта, кривые — из рядов
    названного источника, и 14.09.2026 это дало PDF с таблицей «35 394 →
    60 101» и кривой до 1 058 129 по одному домену (Z10).

    Оракул кладёт в базу **оба** источника нарочно: в одном источнике
    совпадение выполняется само собой, и дефект остаётся невидимым ровно так
    же, как умолчание из урока L107.
    """
    ruleset = await _stored_ruleset(db_session, VERSION, active=True)
    project = await _stored_project(db_session, "wickes.example")
    await _stored_verdict(
        db_session,
        project,
        ruleset,
        Group.GOOD,
        source=MetricSource.FIXTURE,
        values_a={"org_traffic": 35394.0},
        values_b={"org_traffic": 60101.0},
    )
    await _stored_points(
        db_session,
        project,
        dict.fromkeys(HALF_YEAR, 35394.0) | dict.fromkeys(LAST_HALF, 60101.0),
        source=MetricSource.FIXTURE,
    )
    await _stored_points(
        db_session,
        project,
        dict.fromkeys(HALF_YEAR, 900000.0) | dict.fromkeys(LAST_HALF, 1058129.0),
        source=MetricSource.LIVE,
    )

    by_live = await build_cases(db_session, source=MetricSource.LIVE)
    by_fixture = await build_cases(db_session, source=MetricSource.FIXTURE)

    refused = by_live.by_outcome(CaseOutcome.VERDICT_MISMATCH)
    assert [item.domain for item in refused] == ["wickes.example"]
    assert refused[0].case is None
    assert "fixture" in refused[0].detail and "live" in refused[0].detail
    assert "classify" in refused[0].detail
    assert "вердикт не про эти данные: 1" in "\n".join(by_live.as_lines())
    # Тот же вердикт с его собственными рядами — обычный собранный кейс.
    assert [item.domain for item in by_fixture.by_outcome(CaseOutcome.BUILT)] == ["wickes.example"]


async def test_verdict_without_a_source_does_not_produce_a_case(db_session: AsyncSession) -> None:
    """E3: вердикт вынесен до того, как источник стали записывать.

    Подставить ему `fixture` было бы дешевле всего и означало бы записать в
    базу неправду: часть таких вердиктов посчитана по живым рядам. «Источник
    неизвестен» — это состояние, а не пропуск, и лечится оно бесплатным
    пересчётом.
    """
    ruleset = await _stored_ruleset(db_session, VERSION, active=True)
    project = await _stored_project(db_session, "old.example")
    await _stored_verdict(db_session, project, ruleset, Group.GOOD, source=None)
    await _stored_points(db_session, project, MATCHING_SERIES, source=MetricSource.FIXTURE)

    report = await build_cases(db_session, source=MetricSource.FIXTURE)

    refused = report.by_outcome(CaseOutcome.VERDICT_MISMATCH)
    assert [item.domain for item in refused] == ["old.example"]
    assert "не записывать" in refused[0].detail or "записывать" in refused[0].detail
    assert "classify" in refused[0].detail


async def test_month_bought_into_the_window_after_the_verdict_stops_the_case(
    db_session: AsyncSession,
) -> None:
    """E4: источник тот же, но ряд изменился — числа таблицы уже не его.

    Дыру в окне точки А докупили после классификации. Вердикт продолжает
    показывать старое среднее, кривая — новое; на листе рядом это две разные
    правды об одном месяце.
    """
    ruleset = await _stored_ruleset(db_session, VERSION, active=True)
    project = await _stored_project(db_session, "gap.example")
    await _stored_verdict(db_session, project, ruleset, Group.GOOD)
    bought_later = dict(MATCHING_SERIES)
    bought_later[PERIOD_START] = 400.0
    await _stored_points(db_session, project, bought_later, source=MetricSource.FIXTURE)

    report = await build_cases(db_session, source=MetricSource.FIXTURE)

    refused = report.by_outcome(CaseOutcome.VERDICT_MISMATCH)
    assert [item.domain for item in refused] == ["gap.example"]
    assert "org_traffic" in refused[0].detail
    assert "точка А" in refused[0].detail


def test_metric_bought_after_the_verdict_is_not_a_mismatch() -> None:
    """E5: докупленная метрика — предупреждение, а не отказ (урок L41).

    Сверка смотрит на метрики, которые в вердикте **есть**. Считай она
    расхождением всякую разницу между вердиктом и рядами, нормальный порядок
    прогона (ступень кейса докупает DR после классификации) не давал бы ни
    одного кейса.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})
    series = {
        Metric.ORG_TRAFFIC: MATCHING_SERIES,
        Metric.DR: dict.fromkeys(LAST_HALF, 60.0),
    }

    assert numbers_mismatch(_project(), verdict, series, Windows()) is None
    assert stale_subjects(verdict, series) == (Metric.DR.value,)


def test_period_moved_after_the_verdict_stops_the_case() -> None:
    """E8: период работ правили — точка вердикта стоит не на той границе.

    Числа при этом могут выглядеть правдоподобно: усреднение по окну у другой
    границы даёт другое, но похожее число. Сверять одни только значения
    означало бы пропустить случай, где таблица честно считает не тот период,
    который написан в шапке кейса.
    """
    verdict = _verdict_view({"org_traffic": 1000.0}, {"org_traffic": 2000.0})
    moved = _project(period_start=date(2025, 3, 1))

    reason = numbers_mismatch(moved, verdict, {Metric.ORG_TRAFFIC: MATCHING_SERIES}, Windows())

    assert reason is not None
    assert "точка А" in reason and "2025-03" in reason


async def test_normal_run_order_still_produces_cases(db_session: AsyncSession) -> None:
    """E6: обычный порядок прогона не начинает отказывать из-за сверки.

    Порядок настоящий и в нём есть ловушка: ступень кейса докупает данные
    **после** классификации, и сверка, устроенная как «вердикт равен рядам»,
    отказывала бы каждому кейсу подряд — то есть чинила бы Z10 ценой всего
    остального. Оракул проходит путь целиком и требует собранного кейса без
    повторной классификации.
    """
    await accept(
        db_session,
        parse_csv_text(
            f"{INTAKE_COLUMNS}\nd0.example.com,2025-01-01,2026-06-30,fintech,US,seo,"
            "10,Acme,i.petrov,yes,subdomains,\n",
            origin="test",
        ),
    )
    await collect_all(db_session, AhrefsFixture(), now=date(2026, 9, 15))
    projects = list((await db_session.execute(select(Project))).scalars().all())
    ids = [project.id for project in projects]
    await collect_stage2(db_session, ids, AhrefsFixture(), now=date(2026, 9, 15))

    ruleset = await seed_thresholds(db_session)
    await classify_projects(db_session, projects, source=MetricSource.FIXTURE)
    # Ступень кейса — **после** вердикта: так устроена экономия units.
    await collect_case_data(db_session, ids, AhrefsFixture(), now=date(2026, 9, 15))

    report = await build_cases(db_session, source=MetricSource.FIXTURE)

    assert report.ruleset_version == ruleset.version
    assert report.by_outcome(CaseOutcome.VERDICT_MISMATCH) == []
    built = report.by_outcome(CaseOutcome.BUILT)
    assert [item.domain for item in built] == ["d0.example.com"]
    # Докупленное после вердикта по-прежнему называется вслух, а не отказом.
    assert built[0].stale_subjects
