"""Вычет «счётчик Ahrefs ещё не видит» — только траты текущего ключа (Z49).

Прод, 25.09.2026: владелец сменил ключ Ahrefs, и смета отказала каждому прогону —
«не хватает units: остаток 10000, потрачено помимо счётчика 10460». Вычет брал
живой расход журнала за сутки, не зная, каким ключом он оплачен, и вычитал траты
старого ключа из остатка нового. Остаток принадлежит ключу — значит, и вычитать
из него можно только его траты. Ключ узнаётся по отпечатку в снимке прогона;
прогон без отпечатка открыт до правки и оплачен ключом, которого мы не знаем, —
из остатка текущего он не вычитается.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.budget import spend_summary, uncounted_spend
from ahrefs_cases.collect.run_journal import open_run, system_user
from ahrefs_cases.storage._enums import LedgerKind, RunStatus
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

KEY = "текущий-ключ-для-теста-0123456789abcdef"
OLD = "старый-ключ-для-теста-fedcba9876543210"


def _fp(key: str) -> str:
    """Отпечаток так, как его обещает поставка: первые 12 знаков sha256."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]


@pytest.fixture(autouse=True)
def current_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.ahrefs, "api_key", KEY)


async def _paid(session: AsyncSession, snapshot: dict[str, object], units: int) -> None:
    author = await system_user(session)
    run = Run(
        started_by=author.id, status=RunStatus.DONE, projects_total=1, params_snapshot=snapshot
    )
    session.add(run)
    await session.flush()
    session.add(
        UnitsLedger(run_id=run.id, kind=LedgerKind.SPENT, units_estimated=units, units_actual=units)
    )
    await session.flush()


async def _deducted(session: AsyncSession) -> int:
    return await uncounted_spend(session, now=datetime.now(UTC))


async def test_spend_of_another_key_is_not_deducted(db_session: AsyncSession) -> None:
    """H1: траты прежнего ключа не вычитаются из остатка нового, но расходом остаются."""
    before, spent_before = await _deducted(db_session), (await spend_summary(db_session)).live

    await _paid(db_session, {"provider": "live", "api_key_fp": _fp(OLD)}, 900)

    assert await _deducted(db_session) == before
    assert (await spend_summary(db_session)).live == spent_before + 900


async def test_run_without_fingerprint_is_not_deducted(db_session: AsyncSession) -> None:
    """H2: прогон, открытый до правки, оплачен неизвестным ключом — не вычитается."""
    before = await _deducted(db_session)

    await _paid(db_session, {"provider": "live"}, 700)

    assert await _deducted(db_session) == before


async def test_spend_of_the_current_key_is_deducted(db_session: AsyncSession) -> None:
    """H3: страж от перегиба — траты текущего ключа вычитаются, как раньше."""
    before = await _deducted(db_session)

    await _paid(db_session, {"provider": "live", "api_key_fp": _fp(KEY)}, 500)

    assert await _deducted(db_session) == before + 500


async def test_run_remembers_which_key_pays(db_session: AsyncSession) -> None:
    """H4: прогон записывает отпечаток ключа, а сам ключ — нигде."""
    user = await system_user(db_session)

    run = await open_run(db_session, started_by=user.id, projects_total=1)

    assert run.params_snapshot["api_key_fp"] == _fp(KEY)
    assert KEY not in str(run.params_snapshot)
