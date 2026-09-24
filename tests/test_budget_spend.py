"""Сколько units потрачено — одно правило на все пути.

Примеры приёмки поставки `usage-counts-live-units-only`: R3 (журнал трёх
режимов делится на живой расход и условный без остатка), R4 (домен считается
один раз и только за живую оплату), R5 (нет живого расхода — стоимости на сто
нет), R8 (вычет из остатка и «потрачено» видят одно и то же), R9 (второй путь
к сумме `SPENT` не появляется молча), R10 (удаление проекта стоимость на сто
не двигает).

Точные числа — на пустой базе в транзакции (`db_session`): чужие прогоны
стенда тут не мешают, откат возвращает базу как была.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.budget import spend_summary, uncounted_spend
from ahrefs_cases.collect.run_journal import system_user
from ahrefs_cases.storage._enums import LedgerKind, RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run, RunItem
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

SRC = Path(__file__).resolve().parents[1] / "src" / "ahrefs_cases"

LEDGER_READERS = {
    "collect/budget.py": "правило живёт здесь: все суммы расхода",
    "collect/purchases.py": "не сумма: есть ли строка расхода по домену и endpoint'у",
}
"""Где разрешено спрашивать журнал о строках `SPENT` — поимённо и с причиной.

Список, а не «все, кроме роутеров»: второй путь к той же величине однажды уже
появился законным кодом (роутер экрана расхода), и заметить его можно было
только по числам на экране."""

LIVE = {"provider": "live"}
FIXTURE = {"provider": "fixture"}


async def _run(
    session: AsyncSession,
    snapshot: dict[str, object],
    paid: Mapping[str, int],
    *,
    cached: tuple[str, ...] = (),
) -> Run:
    """Закрытый прогон: строка расхода на каждый оплаченный домен и строка
    кэша на каждый взятый из памяти — как их пишет сбор (`record_spend`,
    `record_cached`)."""
    author = await system_user(session)
    run = Run(
        started_by=author.id,
        status=RunStatus.DONE,
        projects_total=len(paid) + len(cached),
        params_snapshot=snapshot,
    )
    session.add(run)
    await session.flush()
    session.add_all(
        UnitsLedger(
            run_id=run.id,
            kind=LedgerKind.SPENT,
            endpoint="metrics-history",
            target=domain,
            units_estimated=units,
            units_actual=units,
        )
        for domain, units in paid.items()
    )
    session.add_all(
        UnitsLedger(
            run_id=run.id,
            kind=LedgerKind.CACHED,
            endpoint="metrics-history",
            target=domain,
            units_estimated=0,
            units_actual=0,
        )
        for domain in cached
    )
    await session.flush()
    return run


async def test_journal_splits_into_live_and_conditional(db_session: AsyncSession) -> None:
    """R3: живой 300 по двум доменам, fixture 500 по трём, прогон без режима 1."""
    await _run(db_session, LIVE, {"a.example": 150, "b.example": 150})
    await _run(db_session, FIXTURE, {"c.example": 100, "d.example": 200, "e.example": 200})
    await _run(db_session, {}, {"f.example": 1})

    spend = await spend_summary(db_session)

    assert spend.live == 300
    # Прогон без режима живым не считается: настоящим расход признаётся, только
    # когда журнал это знает.
    assert spend.conditional == 501
    assert spend.live_domains == 2
    assert spend.per_hundred() == 15_000


async def test_domain_counts_once_and_only_for_live_payment(db_session: AsyncSession) -> None:
    """R4: шаг 2 по оплаченному домену и fixture-прогон по тем же и новому — домен считается раз."""
    await _run(db_session, LIVE, {"a.example": 150, "b.example": 150})
    await _run(db_session, LIVE, {"a.example": 200})
    await _run(db_session, FIXTURE, {"a.example": 100, "b.example": 100, "c.example": 300})

    spend = await spend_summary(db_session)

    assert spend.live_domains == 2
    assert spend.per_hundred() == 25_000


async def test_no_live_spend_has_no_cost_per_hundred(db_session: AsyncSession) -> None:
    """R5: живых прогонов нет — стоимости на сто нет; живой прогон, взявший всё из кэша, — тоже."""
    await _run(db_session, FIXTURE, {"a.example": 500})

    only_fixture = await spend_summary(db_session)

    assert only_fixture.live == 0
    assert only_fixture.per_hundred() is None

    await _run(db_session, LIVE, {}, cached=("b.example",))

    cached_only = await spend_summary(db_session)

    # За домен из кэша не платили: в знаменатель он не входит, и ноль не
    # выдаётся за «бесплатно».
    assert cached_only.live_domains == 0
    assert cached_only.per_hundred() is None


async def test_deduction_and_spent_ask_one_rule(db_session: AsyncSession) -> None:
    """R8: вычет из остатка и «потрачено» видят 900 живых и не видят 400 fixture."""
    await _run(db_session, LIVE, {"a.example": 900})
    await _run(db_session, FIXTURE, {"b.example": 400})

    deduction = await uncounted_spend(db_session, now=datetime.now(UTC))
    spend = await spend_summary(db_session)

    assert deduction == spend.live == 900


async def test_deleting_a_project_does_not_move_the_cost(db_session: AsyncSession) -> None:
    """R10: проект удалён после живого прогона — потрачено, домены и стоимость на сто прежние."""
    project = Project(
        domain="a.example",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="fintech",
        geo="US",
        service_type="seo",
        client="Acme",
        owner="i.petrov",
        notes="",
    )
    db_session.add(project)
    await db_session.flush()
    run = await _run(db_session, LIVE, {"a.example": 300, "b.example": 300})
    db_session.add(
        RunItem(
            run_id=run.id,
            project_id=project.id,
            raw_domain=project.domain,
            outcome=RunItemOutcome.OK,
            units_actual=300,
        )
    )
    await db_session.flush()
    before = await spend_summary(db_session)

    await db_session.execute(delete(Project).where(Project.id == project.id))
    after = await spend_summary(db_session)

    assert after == before
    assert after.per_hundred() == 30_000


def _spent_readers() -> dict[str, int]:
    """Модули `src/`, спрашивающие о `LedgerKind.SPENT`, → первая такая строка."""
    found: dict[str, int] = {}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "SPENT"
                and isinstance(node.value, ast.Name)
                and node.value.id == "LedgerKind"
            ):
                found.setdefault(path.relative_to(SRC).as_posix(), node.lineno)
    return found


def test_spend_is_summed_in_one_place() -> None:
    """R9: строки `SPENT` читают только объявленные модули.

    Роутер экрана расхода суммировал журнал сам — законным кодом, мимо правила
    «условные units фикстур не расход». Новый читатель журнала обязан либо
    звать `collect/budget.py`, либо встать в `LEDGER_READERS` с причиной.
    """
    readers = _spent_readers()
    stray = {name: line for name, line in readers.items() if name not in LEDGER_READERS}

    assert not stray, (
        f"расход суммируется мимо collect/budget.py: {stray} — позови "
        "budget.spend_summary / live_spend_since или объяви модуль в LEDGER_READERS"
    )
    # Сторож смотрит туда, куда думает: правило на месте и находится сканом.
    assert "collect/budget.py" in readers
