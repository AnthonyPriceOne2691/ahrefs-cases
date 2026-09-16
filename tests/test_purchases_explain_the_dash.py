"""Прочерк в условии вердикта объясняется журналом расхода, а не догадкой.

Примеры приёмки Z25: E1 (журнал молчит — молчим и мы), E2 (шаг 2 не платился —
«не покупали»), E3 (платился, а данных нет — «нет данных»), E4 (условие не про
метрику остаётся как было).

Разница не косметическая: «не покупали» можно докупить, «нет данных» докупать
нечем, и заказчик спрашивает именно это — «вы не купили или не смогли?».
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.routers.projects import _reason
from ahrefs_cases.collect.purchases import bought_metrics
from ahrefs_cases.collect.run_journal import open_run, system_user
from ahrefs_cases.storage._enums import LedgerKind, Metric
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

_STAGE1_ONLY = "stage-one.example"
_STAGE2_TOO = "stage-two.example"


async def _spend(session: AsyncSession, domain: str, endpoints: tuple[str, ...]) -> None:
    user = await system_user(session)
    run = await open_run(session, started_by=user.id, projects_total=1)
    session.add_all(
        [
            UnitsLedger(
                run_id=run.id,
                kind=LedgerKind.SPENT,
                endpoint=endpoint,
                target=domain,
                units_estimated=100,
                units_actual=100,
                rows=12,
            )
            for endpoint in endpoints
        ]
    )
    await session.flush()


async def test_silent_ledger_says_nothing(db_session: AsyncSession) -> None:
    """E1: журнал про домен не знает — ответа нет, и это не «не покупали».

    Данные, собранные до появления журнала, иначе получили бы приговор
    «не покупали» на пустом месте.
    """
    assert await bought_metrics(db_session, "never-seen.example") is None


async def test_stage_one_only_means_not_bought(db_session: AsyncSession) -> None:
    """E2: платили только за трафик — позиции и ссылки не покупали."""
    await _spend(db_session, _STAGE1_ONLY, ("metrics-history",))

    bought = await bought_metrics(db_session, _STAGE1_ONLY)

    assert bought is not None
    assert Metric.ORG_TRAFFIC in bought
    assert Metric.REFDOMAINS not in bought
    assert Metric.KW_TOP3 not in bought


async def test_stage_two_spend_is_visible(db_session: AsyncSession) -> None:
    """E3: платили за позиции и ссылки — покупка видна поимённо."""
    await _spend(
        db_session, _STAGE2_TOO, ("metrics-history", "keywords-history", "refdomains-history")
    )

    bought = await bought_metrics(db_session, _STAGE2_TOO)

    assert bought is not None
    assert {Metric.REFDOMAINS, Metric.KW_TOP3} <= bought


def _check(subject: str, fact: float | None = None) -> dict[str, object]:
    return {
        "subject": subject,
        "fact": fact,
        "threshold": 30.0,
        "passed": False,
        "decisive": False,
        "note": "рост ссылающихся доменов",
    }


def test_empty_fact_without_purchase_says_not_bought() -> None:
    """E2 на уровне ответа API: шаг 2 не платился — «не покупали»."""
    row = _reason(_check("good.refdomains_pct"), frozenset({Metric.ORG_TRAFFIC}))

    assert row.fact_missing == "not_bought"


def test_empty_fact_with_purchase_says_no_data() -> None:
    """E3: платили, а Ahrefs ничего не отдал — докупать нечего."""
    row = _reason(_check("good.refdomains_pct"), frozenset({Metric.REFDOMAINS}))

    assert row.fact_missing == "no_data"


def test_silent_ledger_leaves_the_dash() -> None:
    """E1: журнал молчит — причину не выдумываем."""
    assert _reason(_check("good.refdomains_pct"), None).fact_missing is None


def test_conditions_that_are_not_about_metrics_stay_as_they_were() -> None:
    """E4: «сколько подтверждающих сработало» — не метрика, и объяснять нечего.

    Страж от перегиба: признак ставится только там, где за метрику платят, —
    иначе экран начнёт писать «не покупали» под счётчиками и длительностью.
    """
    assert _reason(_check("good.supporting_required"), frozenset()).fact_missing is None
    assert _reason(_check("org_traffic"), frozenset()).fact_missing is None


def test_a_present_fact_is_never_explained() -> None:
    """Факт есть — объяснять нечего, что бы ни говорил журнал."""
    assert _reason(_check("good.refdomains_pct", 12.0), frozenset()).fact_missing is None
